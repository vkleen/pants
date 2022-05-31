# Copyright 2020 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

"""Rules for the core Python target types.

This is a separate module to avoid circular dependencies. Note that all types used by call sites are
defined in `target_types.py`.
"""

import dataclasses
import logging
import os.path
from collections import defaultdict
from dataclasses import dataclass
from itertools import chain
from textwrap import dedent
from typing import DefaultDict, Dict, Generator, Optional, Tuple, cast

from pants.backend.python.dependency_inference.module_mapper import (
    PythonModuleOwners,
    PythonModuleOwnersRequest,
)
from pants.backend.python.dependency_inference.rules import PythonInferSubsystem, import_rules
from pants.backend.python.goals.setup_py import InvalidEntryPoint
from pants.backend.python.subsystems.setup import PythonSetup
from pants.backend.python.target_types import (
    EntryPoint,
    InterpreterConstraintsField,
    PexBinariesGeneratorTarget,
    PexBinary,
    PexBinaryDependenciesField,
    PexEntryPointField,
    PexEntryPointsField,
    PythonDistributionDependenciesField,
    PythonDistributionEntryPoint,
    PythonDistributionEntryPointsField,
    PythonFilesGeneratorSettingsRequest,
    PythonProvidesField,
    PythonResolveField,
    ResolvedPexEntryPoint,
    ResolvedPythonDistributionEntryPoints,
    ResolvePexEntryPointRequest,
    ResolvePythonDistributionEntryPointsRequest,
)
from pants.backend.python.util_rules.interpreter_constraints import interpreter_constraints_contains
from pants.engine.addresses import Address, Addresses, UnparsedAddressInputs
from pants.engine.fs import GlobMatchErrorBehavior, PathGlobs, Paths
from pants.engine.rules import Get, MultiGet, collect_rules, rule
from pants.engine.target import (
    Dependencies,
    DependenciesRequest,
    ExplicitlyProvidedDependencies,
    FieldSet,
    GeneratedTargets,
    GenerateTargetsRequest,
    InjectDependenciesRequest,
    InjectedDependencies,
    InvalidFieldException,
    TargetFilesGeneratorSettings,
    TargetFilesGeneratorSettingsRequest,
    Targets,
    ValidatedDependencies,
    ValidateDependenciesRequest,
    WrappedTarget,
)
from pants.engine.unions import UnionMembership, UnionRule
from pants.source.source_root import SourceRoot, SourceRootRequest
from pants.util.docutil import doc_url
from pants.util.frozendict import FrozenDict
from pants.util.ordered_set import OrderedSet
from pants.util.strutil import bullet_list, softwrap

logger = logging.getLogger(__name__)


@rule
def python_files_generator_settings(
    _: PythonFilesGeneratorSettingsRequest,
    python_infer: PythonInferSubsystem,
) -> TargetFilesGeneratorSettings:
    return TargetFilesGeneratorSettings(add_dependencies_on_all_siblings=not python_infer.imports)


# -----------------------------------------------------------------------------------------------
# `pex_binary` target generation rules
# -----------------------------------------------------------------------------------------------


class GenerateTargetsFromPexBinaries(GenerateTargetsRequest):
    # TODO: This can be deprecated in favor of `parametrize`.
    generate_from = PexBinariesGeneratorTarget


@rule
async def generate_targets_from_pex_binaries(
    request: GenerateTargetsFromPexBinaries,
    union_membership: UnionMembership,
) -> GeneratedTargets:
    generator_addr = request.template_address
    entry_points_field = request.generator[PexEntryPointsField].value or []
    overrides = request.require_unparametrized_overrides()

    # Note that we don't check for overlap because it seems unlikely to be a problem.
    # If it does, we should add this check. (E.g. `path.to.app` and `path/to/app.py`)

    def create_pex_binary(entry_point_spec: str) -> PexBinary:
        return PexBinary(
            {
                PexEntryPointField.alias: entry_point_spec,
                **request.template,
                # Note that overrides comes last to make sure that it indeed overrides.
                **overrides.pop(entry_point_spec, {}),
            },
            # ":" is a forbidden character in target names
            generator_addr.create_generated(entry_point_spec.replace(":", "-")),
            union_membership,
            residence_dir=generator_addr.spec_path,
        )

    pex_binaries = [create_pex_binary(entry_point) for entry_point in entry_points_field]

    if overrides:
        raise InvalidFieldException(
            softwrap(
                f"""
                Unused key in the `overrides` field for {generator_addr}:
                {sorted(overrides)}

                Tip: if you'd like to override a field's value for every `{PexBinary.alias}` target
                generated by this target, change the field directly on this target rather than using
                the `overrides` field.
                """
            )
        )

    return GeneratedTargets(request.generator, pex_binaries)


# -----------------------------------------------------------------------------------------------
# `pex_binary` rules
# -----------------------------------------------------------------------------------------------


@rule(desc="Determining the entry point for a `pex_binary` target")
async def resolve_pex_entry_point(request: ResolvePexEntryPointRequest) -> ResolvedPexEntryPoint:
    ep_val = request.entry_point_field.value
    if ep_val is None:
        return ResolvedPexEntryPoint(None, file_name_used=False)
    address = request.entry_point_field.address

    # We support several different schemes:
    #  1) `path.to.module` => preserve exactly.
    #  2) `path.to.module:func` => preserve exactly.
    #  3) `app.py` => convert into `path.to.app`.
    #  4) `app.py:func` => convert into `path.to.app:func`.

    # If it's already a module (cases #1 and #2), simply use that. Otherwise, convert the file name
    # into a module path (cases #3 and #4).
    if not ep_val.module.endswith(".py"):
        return ResolvedPexEntryPoint(ep_val, file_name_used=False)

    # Use the engine to validate that the file exists and that it resolves to only one file.
    full_glob = os.path.join(address.spec_path, ep_val.module)
    entry_point_paths = await Get(
        Paths,
        PathGlobs(
            [full_glob],
            glob_match_error_behavior=GlobMatchErrorBehavior.error,
            description_of_origin=f"{address}'s `{request.entry_point_field.alias}` field",
        ),
    )
    # We will have already raised if the glob did not match, i.e. if there were no files. But
    # we need to check if they used a file glob (`*` or `**`) that resolved to >1 file.
    if len(entry_point_paths.files) != 1:
        raise InvalidFieldException(
            softwrap(
                f"""
                Multiple files matched for the `{request.entry_point_field.alias}`
                {ep_val.spec!r} for the target {address}, but only one file expected. Are you using
                a glob, rather than a file name?

                All matching files: {list(entry_point_paths.files)}.
                """
            )
        )
    entry_point_path = entry_point_paths.files[0]
    source_root = await Get(
        SourceRoot,
        SourceRootRequest,
        SourceRootRequest.for_file(entry_point_path),
    )
    stripped_source_path = os.path.relpath(entry_point_path, source_root.path)
    module_base, _ = os.path.splitext(stripped_source_path)
    normalized_path = module_base.replace(os.path.sep, ".")
    return ResolvedPexEntryPoint(
        dataclasses.replace(ep_val, module=normalized_path), file_name_used=True
    )


class InjectPexBinaryEntryPointDependency(InjectDependenciesRequest):
    inject_for = PexBinaryDependenciesField


@rule(desc="Inferring dependency from the pex_binary `entry_point` field")
async def inject_pex_binary_entry_point_dependency(
    request: InjectPexBinaryEntryPointDependency,
    python_infer_subsystem: PythonInferSubsystem,
    python_setup: PythonSetup,
) -> InjectedDependencies:
    if not python_infer_subsystem.entry_points:
        return InjectedDependencies()
    original_tgt = await Get(WrappedTarget, Address, request.dependencies_field.address)
    entry_point_field = original_tgt.target.get(PexEntryPointField)
    if entry_point_field.value is None:
        return InjectedDependencies()

    explicitly_provided_deps, entry_point = await MultiGet(
        Get(ExplicitlyProvidedDependencies, DependenciesRequest(original_tgt.target[Dependencies])),
        Get(ResolvedPexEntryPoint, ResolvePexEntryPointRequest(entry_point_field)),
    )
    if entry_point.val is None:
        return InjectedDependencies()

    owners = await Get(
        PythonModuleOwners,
        PythonModuleOwnersRequest(
            entry_point.val.module,
            resolve=original_tgt.target[PythonResolveField].normalized_value(python_setup),
        ),
    )
    address = original_tgt.target.address
    explicitly_provided_deps.maybe_warn_of_ambiguous_dependency_inference(
        owners.ambiguous,
        address,
        # If the entry point was specified as a file, like `app.py`, we know the module must
        # live in the pex_binary's directory or subdirectory, so the owners must be ancestors.
        owners_must_be_ancestors=entry_point.file_name_used,
        import_reference="module",
        context=softwrap(
            f"""
            The pex_binary target {address} has the field
            `entry_point={repr(entry_point_field.value.spec)}`, which
            maps to the Python module `{entry_point.val.module}`
            """
        ),
    )
    maybe_disambiguated = explicitly_provided_deps.disambiguated(
        owners.ambiguous, owners_must_be_ancestors=entry_point.file_name_used
    )
    unambiguous_owners = owners.unambiguous or (
        (maybe_disambiguated,) if maybe_disambiguated else ()
    )
    return InjectedDependencies(unambiguous_owners)


# -----------------------------------------------------------------------------------------------
# `python_distribution` rules
# -----------------------------------------------------------------------------------------------


_EntryPointsDictType = Dict[str, Dict[str, str]]


def _classify_entry_points(
    all_entry_points: _EntryPointsDictType,
) -> Generator[Tuple[bool, str, str, str], None, None]:
    """Looks at each entry point to see if it is a target address or not.

    Yields tuples: is_target, category, name, entry_point_str.
    """
    for category, entry_points in all_entry_points.items():
        for name, entry_point_str in entry_points.items():
            yield (
                entry_point_str.startswith(":") or "/" in entry_point_str,
                category,
                name,
                entry_point_str,
            )


@rule(desc="Determining the entry points for a `python_distribution` target")
async def resolve_python_distribution_entry_points(
    request: ResolvePythonDistributionEntryPointsRequest,
) -> ResolvedPythonDistributionEntryPoints:
    if request.entry_points_field:
        if request.entry_points_field.value is None:
            return ResolvedPythonDistributionEntryPoints()
        address = request.entry_points_field.address
        all_entry_points = cast(_EntryPointsDictType, request.entry_points_field.value)

    elif request.provides_field:
        address = request.provides_field.address
        provides_field_value = cast(
            _EntryPointsDictType, request.provides_field.value.kwargs.get("entry_points") or {}
        )

        if provides_field_value:
            all_entry_points = provides_field_value
        else:
            return ResolvedPythonDistributionEntryPoints()
    else:
        return ResolvedPythonDistributionEntryPoints()

    classified_entry_points = list(_classify_entry_points(all_entry_points))

    # Pick out all target addresses up front, so we can use MultiGet later.
    #
    # This calls for a bit of trickery however (using the "y_by_x" mapping dicts), so we keep track
    # of which address belongs to which entry point. I.e. the `address_by_ref` and
    # `binary_entry_point_by_address` variables.

    target_refs = [
        entry_point_str for is_target, _, _, entry_point_str in classified_entry_points if is_target
    ]

    # Intermediate step, as Get(Targets) returns a deduplicated set.. which breaks in case of
    # multiple input refs that maps to the same target.
    target_addresses = await Get(
        Addresses, UnparsedAddressInputs(target_refs, owning_address=address)
    )
    address_by_ref = dict(zip(target_refs, target_addresses))
    targets = await Get(Targets, Addresses, target_addresses)

    # Check that we only have targets with a pex entry_point field.
    for target in targets:
        if not target.has_field(PexEntryPointField):
            raise InvalidEntryPoint(
                softwrap(
                    f"""
                    All target addresses in the entry_points field must be for pex_binary targets,
                    but the target {address} includes the value {target.address}, which has the
                    target type {target.alias}.

                    Alternatively, you can use a module like "project.app:main".
                    See {doc_url('python-distributions')}.
                    """
                )
            )

    binary_entry_points = await MultiGet(
        Get(
            ResolvedPexEntryPoint,
            ResolvePexEntryPointRequest(target[PexEntryPointField]),
        )
        for target in targets
    )
    binary_entry_point_by_address = {
        target.address: entry_point for target, entry_point in zip(targets, binary_entry_points)
    }

    entry_points: DefaultDict[str, Dict[str, PythonDistributionEntryPoint]] = defaultdict(dict)

    # Parse refs/replace with resolved pex entry point, and validate console entry points have function.
    for is_target, category, name, ref in classified_entry_points:
        owner: Optional[Address] = None
        if is_target:
            owner = address_by_ref[ref]
            entry_point = binary_entry_point_by_address[owner].val
            if entry_point is None:
                logger.warning(
                    softwrap(
                        f"""
                        The entry point {name} in {category} references a pex_binary target {ref}
                        which does not set `entry_point`. Skipping.
                        """
                    )
                )
                continue
        else:
            entry_point = EntryPoint.parse(ref, f"{name} for {address} {category}")

        if category in ["console_scripts", "gui_scripts"] and not entry_point.function:
            url = "https://python-packaging.readthedocs.io/en/latest/command-line-scripts.html#the-console-scripts-entry-point"
            raise InvalidEntryPoint(
                dedent(
                    f"""\
                Every entry point in `{category}` for {address} must end in the format `:my_func`,
                but {name} set it to {entry_point.spec!r}. For example, set
                `entry_points={{"{category}": {{"{name}": "{entry_point.module}:main}} }}`.
                See {url}.
                """
                )
            )

        entry_points[category][name] = PythonDistributionEntryPoint(entry_point, owner)

    return ResolvedPythonDistributionEntryPoints(
        FrozenDict(
            {category: FrozenDict(entry_points) for category, entry_points in entry_points.items()}
        )
    )


class InjectPythonDistributionDependencies(InjectDependenciesRequest):
    inject_for = PythonDistributionDependenciesField


@rule
async def inject_python_distribution_dependencies(
    request: InjectPythonDistributionDependencies, python_infer_subsystem: PythonInferSubsystem
) -> InjectedDependencies:
    """Inject dependencies that we can infer from entry points in the distribution."""
    if not python_infer_subsystem.entry_points:
        return InjectedDependencies()

    original_tgt = await Get(WrappedTarget, Address, request.dependencies_field.address)
    explicitly_provided_deps, distribution_entry_points, provides_entry_points = await MultiGet(
        Get(ExplicitlyProvidedDependencies, DependenciesRequest(original_tgt.target[Dependencies])),
        Get(
            ResolvedPythonDistributionEntryPoints,
            ResolvePythonDistributionEntryPointsRequest(
                entry_points_field=original_tgt.target[PythonDistributionEntryPointsField]
            ),
        ),
        Get(
            ResolvedPythonDistributionEntryPoints,
            ResolvePythonDistributionEntryPointsRequest(
                provides_field=original_tgt.target[PythonProvidesField]
            ),
        ),
    )

    address = original_tgt.target.address
    all_module_entry_points = [
        (category, name, entry_point)
        for category, entry_points in chain(
            distribution_entry_points.explicit_modules.items(),
            provides_entry_points.explicit_modules.items(),
        )
        for name, entry_point in entry_points.items()
    ]
    all_module_owners = iter(
        await MultiGet(
            Get(PythonModuleOwners, PythonModuleOwnersRequest(entry_point.module, resolve=None))
            for _, _, entry_point in all_module_entry_points
        )
    )
    module_owners: OrderedSet[Address] = OrderedSet()
    for (category, name, entry_point), owners in zip(all_module_entry_points, all_module_owners):
        field_str = repr({category: {name: entry_point.spec}})
        explicitly_provided_deps.maybe_warn_of_ambiguous_dependency_inference(
            owners.ambiguous,
            address,
            import_reference="module",
            context=softwrap(
                f"""
                The python_distribution target {address} has the field
                `entry_points={field_str}`, which maps to the Python module
                `{entry_point.module}`
                """
            ),
        )
        maybe_disambiguated = explicitly_provided_deps.disambiguated(owners.ambiguous)
        unambiguous_owners = owners.unambiguous or (
            (maybe_disambiguated,) if maybe_disambiguated else ()
        )
        module_owners.update(unambiguous_owners)

    return InjectedDependencies(
        Addresses(module_owners)
        + distribution_entry_points.pex_binary_addresses
        + provides_entry_points.pex_binary_addresses
    )


# -----------------------------------------------------------------------------------------------
# Dependency validation
# -----------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class DependencyValidationFieldSet(FieldSet):
    required_fields = (InterpreterConstraintsField,)

    interpreter_constraints: InterpreterConstraintsField


class PythonValidateDependenciesRequest(ValidateDependenciesRequest):
    field_set_type = DependencyValidationFieldSet


@rule
async def validate_python_dependencies(
    request: PythonValidateDependenciesRequest,
    python_setup: PythonSetup,
) -> ValidatedDependencies:
    dependencies = await MultiGet(Get(WrappedTarget, Address, d) for d in request.dependencies)

    # Validate that the ICs for dependencies are all compatible with our own.
    target_ics = request.field_set.interpreter_constraints.value_or_global_default(python_setup)
    non_subset_items = []
    for dep in dependencies:
        if not dep.target.has_field(InterpreterConstraintsField):
            continue
        dep_ics = dep.target[InterpreterConstraintsField].value_or_global_default(python_setup)
        if not interpreter_constraints_contains(
            dep_ics, target_ics, python_setup.interpreter_universe
        ):
            non_subset_items.append(f"{dep_ics}: {dep.target.address}")

    if non_subset_items:
        raise InvalidFieldException(
            softwrap(
                f"""
            The target {request.field_set.address} has the `interpreter_constraints` {target_ics},
            which are not a subset of the `interpreter_constraints` of some of its dependencies:

            {bullet_list(sorted(non_subset_items))}

            To fix this, you should likely adjust {request.field_set.address}'s
            `interpreter_constraints` to match the narrowest range in the above list.
            """
            )
        )

    return ValidatedDependencies()


def rules():
    return (
        *collect_rules(),
        *import_rules(),
        UnionRule(TargetFilesGeneratorSettingsRequest, PythonFilesGeneratorSettingsRequest),
        UnionRule(GenerateTargetsRequest, GenerateTargetsFromPexBinaries),
        UnionRule(InjectDependenciesRequest, InjectPexBinaryEntryPointDependency),
        UnionRule(InjectDependenciesRequest, InjectPythonDistributionDependencies),
        UnionRule(ValidateDependenciesRequest, PythonValidateDependenciesRequest),
    )
