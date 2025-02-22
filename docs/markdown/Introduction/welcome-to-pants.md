---
title: "Welcome to Pants!"
slug: "welcome-to-pants"
hidden: false
createdAt: "2020-02-21T17:44:28.054Z"
updatedAt: "2022-03-09T22:12:20.097Z"
---
What is Pants?
==============

Pants is a fast, scalable, user-friendly build and developer workflow system for codebases of all sizes, including yours! 

What does Pants do?
===================

Pants installs, orchestrates and runs dozens of standard underlying tools - compilers, code generators, dependency resolvers, test runners, linters, formatters, packagers, REPLs and more - composing them into a single stable, hermetic toolchain, and speeding up your workflows via caching and concurrency.

Pants is designed to be easy to adopt, use, and extend. It doesn't require you to refactor your codebase or to create and maintain massive amounts of build metadata. You invoke it directly on source files and directories, so it doesn't require users to adopt a new conceptual model.

Pants is currently focused on Python, Go, Java, Scala, Shell, and Docker, with more languages and frameworks coming soon. [The Pants community](doc:the-pants-community) is friendly and helpful, and supported by [Toolchain](https://toolchain.com/), a venture-backed company whose mission is to enable fast, stable, ergonomic developer workflows for everyone.

Who is Pants for?
=================

Pants is useful for repos of all sizes, but is particularly valuable for those containing multiple distinct but interdependent pieces.

Pants works well with (but does not require) a [_monorepo_ architecture](https://blog.pantsbuild.org/the-monorepo-approach-to-code-management/): a codebase containing multiple projects—often using multiple programming languages and frameworks—in a single unified repository. If you want to scale your codebase without breaking it up into multiple disconnected repos, with all the versioning and maintenance headaches that causes, Pants provides the tooling for you to do so effectively.

What are the main features of Pants?
====================================

Pants is designed for fast, consistent, ergonomic builds. Some noteworthy features include:

- Dependency modeling using static analysis instead of handwritten metadata
- Fine-grained invalidation
- Shared result caching
- Concurrent and remote execution
- Support for dependency lockfiles to prevent supply chain attacks
- A unified interface across all tools and languages
- Extensibility and customizability via a plugin API
- Code introspection features

Which languages and frameworks does Pants support?
==================================================

- Pants [ships](page:language-support) with support for [Python](doc:python), [Go](doc:go), [Java](doc:jvm-overview), [Scala](doc:jvm-overview) and [Shell](doc:shell).
- Pants supports a wide range of code generators (such as Thrift, Protobuf, Scrooge and Avro), linters and formatters, and it is easy to add support for new or custom ones
- Pants can create standalone binaries, [Docker images](doc:docker), AWS Lambdas and GCP Cloud Functions

We're listening to the community for which languages, frameworks and tools we should support next, so let us know about your needs by [opening an issue](https://github.com/pantsbuild/pants/issues/new/choose) on GitHub or [chatting with us](doc:the-pants-community) about it on the community Slack!  
Pants was designed for extensibility, and we welcome [contributions](doc:contributor-overview)!

How does Pants work?
====================

The core of Pants is its execution engine, which sequences and coordinates all the underlying work. The engine is written in Rust, for performance. The underlying work is performed by executing _rules_, which are typed Python 3 async coroutines for familiarity and simplicity. 

The engine is designed so that fine-grained invalidation, concurrency, hermeticity, caching, and remote execution happen naturally, without rule authors needing to think about it.

See [here](doc:how-does-pants-work) for more details about the Pants engine.

Is Pants similar to X?
======================

Pants (v2) is a leap forward in the evolution of build systems, a category that runs from the venerable Make through Ant, Maven, Gradle and SBT, to Bazel, Please, Buck, Pants v1 and others. 

Its design leans on ideas and inspiration from these earlier tools, while optimizing not just for speed and correctness, but also for ease of adoption, ease of use and ease of extension, all for real-world use cases at a variety of teams.

Who uses Pants?
===============

Pants is making engineering teams productive and happy at a range of companies and organizations. See a sample of them [here](page:who-uses-pants)!

Who develops Pants?
===================

Pants is an open-source software project, developed at [github.com/pantsbuild/pants](https://github.com/pantsbuild/pants). Pants is released under the [Apache License 2.0](https://github.com/pantsbuild/pants/blob/master/LICENSE).

[Toolchain](https://toolchain.com/) is the lead sponsor of the Pants project.

> 📘 Pants v2 vs. v1
> 
> This documentation is for Pants v2, which is a new system built from the ground up, based on lessons from past work on Pants v1, as well valued feedback from the user community. See [\<https://v1.pantsbuild.org>](https://v1.pantsbuild.org/) for Pants v1 documentation.
