---
title: "repl"
slug: "python-repl-goal"
excerpt: "Open a REPL for interactive development."
hidden: false
createdAt: "2020-03-16T16:19:56.329Z"
updatedAt: "2022-02-09T01:01:10.431Z"
---
Pants will load a [REPL](https://en.wikipedia.org/wiki/REPL) with all of your specified source code and any of its third-party dependencies, which allows you to import those values.

IPython
-------

In addition to the default Python shell, Pants supports the improved [IPython shell](https://ipython.org).

To use IPython, run `pants repl --shell=ipython`. To permanently use IPython, add this to your `pants.toml`:

```toml pants.toml
[repl]
shell = "ipython"
```

You can change IPython's version with `[ipython].version`. If you change it, Pants's default lockfile for IPython will not work. Either set the `lockfile` option to a custom path or `"<none>"` to opt-out. See [Third-party dependencies](doc:python-third-party-dependencies#tool-lockfiles).

```toml pants.toml
[ipython]
version = "ipython>=8.0.0"
lockfile = "3rdparty/python/ipython_lock.txt"
```

If you set the `version` lower than IPython 7, then you must set `[ipython].ignore_cwd = false` to avoid Pants setting an option that did not exist in earlier IPython releases.

> 📘 Python 2 support
> 
> Pants uses IPython 7 by default, which does not work with Python 2. You can override `version` to use IPython 5. As mentioned above, you must set `ignore_cwd = false`.
> 
> ```toml
> [ipython]
> version = "ipython<6"
> lockfile = "3rdparty/python/ipython_lock.txt"
> ignore_cwd = false
> ```
> 
> You can even use IPython 7 for Python 3 code, and IPython 5 for Python 2 code:
> 
> ```toml
> [ipython]
> version = "ipython==7.16.1 ; python_version >= '3.6'"
> extra_requirements.add = ["ipython<6 ; python_version == '2.7'"]
> lockfile = "3rdparty/python/ipython_lock.txt"
> ignore_cwd = false
> ```

Examples
--------

```text Shell
$ pants repl helloworld/greet/greeting.py

Python 3.7.6 (default, Feb 26 2020, 08:28:08)
[Clang 11.0.0 (clang-1100.0.33.8)] on darwin
Type "help", "copyright", "credits" or "license" for more information.
(InteractiveConsole)
>>> from helloworld.greet.greeting import Greeter
>>> Greeter().greet("Pants")
'buenas tardes, Pants!'
>>> from translate import Translator
>>> Translator(to_lang="fr").translate("Good morning.")
'Salut.'
```

This will not load any of your code:

```text Shell
❯ pants repl --shell=ipython
Python 3.9.12 (main, Mar 26 2022, 15:45:34)
Type 'copyright', 'credits' or 'license' for more information
IPython 7.34.0 -- An enhanced Interactive Python. Type '?' for help.

In [1]: 21 * 4
Out[1]: 84
```

`pants repl ::` will load all your code.

> 📘 Tip: how to exit the REPL
> 
> Either type `exit()` and hit enter, or press `ctrl+d`.
