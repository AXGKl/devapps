# Plugins

Here is how you create or extend tools with plugins, callable like `<toolname> <pluginname> [plugin flags]`.

!!! note "Git Analogy"
    In this terminology, "git" would be the name of the tool, "checkout" would be the name of the plugin.




## Defining a **New** Tool

In your `pyproject.toml` add the name of the tool within the `scripts` section like so:

```python lp hide_cmd=True mode=python
from devapp.tools import read_file, write_file
fn, sect = 'pyproject.toml', '[tool.poetry.scripts]'
app = '\nmyapp = "devapp.plugin_tools:main"'
s = read_file(fn)
if not app in s:
    s = s.replace(sect, sect + app)
    write_file(fn, s)
print(sect + app)
```

This makes the tool available, with no plugins yet:

```bash lp  fmt=xt_flat session=plugins
[{"cmd": "poetry install", "timeout": 10}, "mytool -h"]
```

We are ready to create plugins:

Plugins must reside within `<package>/plugins/<tool_name>_<package_name>/` subdirectory of packages of the current repo. 

The package name at the end is to allow "higher order repos" to supply plugins with same name but changed behaviour.

For the demo we pick the `devapp` package within this repo, `devapps`:

```bash lp  fmt=xt_flat session=plugins
mkdir -p "src/devapp/plugins/myapp_devapp"
```

Then we create a demo plugin:

```python lp fn=src/devapp/plugins/myapp_devapp/say_hello.py mode=make_file
"""
Saying Hello
"""


from functools import partial

from devapp.app import run_app, do, app
from devapp.tools import FLG


class Flags:
    'Simple Hello World'

    autoshort = 'g'  # all short forms for our flags prefixed with this

    class name:
        n = 'Who shall be greeted'
        d = 'User'


# --------------------------------------------------------------------------- app
def greet(name):
    print('Hey, %s!' % name)
    app.info('greeted', name=name)


def run():
    do(greet, name=FLG.name)


main = partial(run_app, run, flags=Flags)
```
 
The plugin is now available:

```bash lp  fmt=xt_flat session=plugins
['myapp sh -h', 'myapp sh -gn Joe']
```


- Further plugins for our `myapp` tool are now simply added into this directory
- Higher order repos can add their own plugins for `myapp`, following the directory convention given above



```python lp silent=True mode=python
# cleaning up: 
from devapp.tools import read_file, write_file
fn = 'pyproject.toml'
app = '\nmyapp = "devapp.plugin_tools:main"'
write_file(fn, read_file(fn).replace(app, ''))
```

```bash lp  silent=True
/bin/rm -rf "src/devapp/plugins/myapp_devapp"
```









