# Building a Portable AppImage for a Python GTK4 Application

Modern Linux ecosystems are powerful but highly fragmented. Differences in distributions, library versions, filesystem layouts, and package managers make it difficult to deliver a single binary that runs reliably everywhere. Traditional packaging formats such as .deb or .rpm tightly couple an application to a specific distribution family and dependency set, increasing maintenance cost and slowing down releases. AppImage addresses this problem by providing a self-contained application format that bundles the executable together with all required runtime dependencies, enabling developers to ship one artifact that works across most Linux distributions without installation or system modification.

In this article we will build simple GTK4 application with Python. Why? Why? Because GTK4 is a modern toolkit, and when combined with Python it becomes an excellent choice for rapid prototyping. It also demonstrates the typical dependency-hell issues related to Linux package distribution.

The goal is to create a package that can be executed on the most popular Linux distributions, including Debian, Ubuntu, Fedora, CentOS, and Arch.

This tutorial uses Ubuntu 24.04 as the development environment.

## Prepare an application

For packaging some application is required. It will be a Poetry-based Python project.
To prevent the host system from being polluted by unnecessary packages, all development will be performed inside a virtual environment.
In this tutorial, all files will be located inside the `sandbox` folder, referenced by the `SANDBOX_FOLDER` environment variable.

``` sh
SANDBOX_FOLDER=sandbox
mkdir -p ${SANDBOX_FOLDER}
cd ${SANDBOX_FOLDER}
# Ubuntu 24.04 has no alias to python by default, so it is called as python3
python3 -m venv ./venv
. ./venv/bin/activate
pip install poetry
```

The next step is to initialize the project. Let's call it `gtk-serpent`.

``` sh
poetry new gtk-serpent
```

Now, `${SANDBOX_FOLDER}` should look like this:

```
.
├── gtk-serpent
│   ├── pyproject.toml
│   ├── README.md
│   ├── src
│   │   └── gtk_serpent
│   │       └── __init__.py
│   └── tests
│       └── __init__.py
└── venv
 
```

To be able to create a GTK4 application, PyGObject is required. The idea is to avoid using the PyGObject version provided by Ubuntu, and instead install it as a Python dependency for the project:

```sh
cd ./gtk-serpent/
poetry add pygobject@^3.54
```

After this, a simple “Hello World” application can be created:

```sh
cd src/gtk_serpent/
cat > application.py << EOF
> import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk


class GtkSerpentApplication(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.example.gtk-serpent")
        GLib.set_application_name('GTKSerpent awesome GTK4 application')

    def do_activate(self):
        window = Gtk.ApplicationWindow(application=self, title="GTKSerpent")
        window.present()

def main():
    app = GtkSerpentApplication()
    app.run()

if __name__ == "__main__":
    main()
> EOF
```

Next, add an entry point for the application to the `pyproject.toml` file:

```toml
[tool.poetry.scripts]
gtk-serpent = "gtk_serpent.application:main"
```

The project is now ready to be installed and verified inside the virtual environment:

```sh
# generate python packages for our project, they will be placed to ${SANDBOX_FOLDER}/dist folder
poetry build
# Install our project to be able to validate it
poetry install
# start it
gtk-serpent
```

If everything went smoothly, you should now see a small GTK4 window with the title “GTKSerpent”.

## Appimage

Now it is possible to create an AppImage that contains the `gtk-serpent` code and can run on different Linux platforms.

The AppImage will be generated using [appimage-builder](https://github.com/AppImageCrafters/appimage-builder).

For this tutorial, it will be installed using pip into the virtual environment already used for the `gtk-serpent` project. 
Other installation methods and details could be found [here](https://appimage-builder.readthedocs.io/en/latest/intro/install.html)

```sh
cd ${SANDBOX_FOLDER}
# Make sure that virtualenv still active, uncomment next line if required
#. ./venv/bin/activate
pip install appimage-builder
```

To keep the project structure clean, all packaging routines will be performed inside `${SANDBOX_FOLDER}/appimage`:

```sh
mkdir -p ${SANDBOX_FOLDER}/appimage
cd ${SANDBOX_FOLDER}/appimage
mkdir AppDir
```

First step is to generate a recipe for the future appimage. This is a YAML file which contains instructions on how image has to be built. 

```sh
appimage-builder --generate
```

It will be a prompt for new recipe parameters. Fill them in as shown in the example below:

```
INFO:Generator:Searching AppDir
? ID [Eg: com.example.app]: com.example.gtk-serpent
? Application Name: gtk-serpent
? Icon: utilities-terminal
? Executable path relative to AppDir [usr/bin/app]: usr/bin/python3
? Arguments [Default: $@]: $APPDIR/usr/bin/gtk-serpent $@
? Version [Eg: 1.0.0]: 0.1.0
? Update Information [Default: guess]: None
? Architecture: amd64
```

This will generate a skeleton for the `appimage-builder` recipe, but it requires a few modifications.

The target image will be built using APT as the binary source.
By default, it uses the Google repository, which is defined in the `AppDir->apt->sources` section:

```yaml
AppDir:
..........................
apt:
    arch: []
    allow_unauthenticated: true
    sources:
    - sourceline: deb [arch=amd64] https://dl.google.com/linux/chrome/deb/ 
        stable main
    include: []
..........................
```

This is definitely not what we want, so let’s change it to Ubuntu:

```yaml
AppDir:
..........................
apt:
    arch: []
    allow_unauthenticated: true
    sources:
      - sourceline: 'deb [arch=amd64] http://archive.ubuntu.com/ubuntu/ noble main restricted universe multiverse'
        key_url: 'http://keyserver.ubuntu.com/pks/lookup?op=get&search=0x871920D1991BC93C'
    include: []
..........................
```

The next issue with the generated recipe is that our Python package is not included. This could be achieved by adding a `script` section to the recipe:

```yaml
script:
  # Remove any previous build
  - rm -rf AppDir  | true
  # Install application dependencies. 
  - python3 -m pip install --ignore-installed --prefix=/usr --root=AppDir ../gtk-serpent/dist/gtk_serpent-0.1.0-py3-none-any.whl
```

At this point `gtk-serpent` will be deployed to the AppDir. However, required libraries such as `libgtk*` or `libcairo*` are still not deployed. Even python is absent in the target package. This is the most challenging part: the target package should contain a minimal set of libraries required to run our Python code.
Let’s define the required packages in the recipe:

```yaml
AppDir:
  apt:
    include:
      - python3
      - gir1.2-gtk-4.0 
      - libgirepository-2.0-dev 
      - libcairo2-dev
      - pkg-config
      - python3-dev
      - gir1.2-gtk-4.0
      - libgtk-4-1
      - libwayland-client0
      - libglapi-mesa
```

Also we have to tweak the runtime: `PYTHONHOME` and `PYTHONPATH` are required to be set:

```yaml
AppDir:
  runtime:
    env:
      PYTHONHOME: '${APPDIR}/usr'
      PYTHONPATH: '${APPDIR}/usr/lib/python3.12/site-packages'
```

Finally, there is an [issue](https://github.com/AppImageCrafters/AppRun/issues/65) with `glibc` resolution that prevents the resulting binary from running, so a small workaround is required:

```yaml
AppDir:
  after_runtime:
    - cd "$TARGET_APPDIR/runtime/compat" && ln -s usr/lib64 . 
``` 

## Testing
As stated at the beginning, we want to run the binary on the most popular Linux distributions. But how can this be verified?
`appimage-builder` provides a convenient tool to verify the application on different platforms using Docker.
The generated recipe contains a `test` section where the application is executed on different platforms:

```yaml
AppDir:
  test:
    fedora-30:
      image: appimagecrafters/tests-env:fedora-30
      command: ./AppRun
      use_host_x: true
    debian-stable:
      image: appimagecrafters/tests-env:debian-stable
      command: ./AppRun
      use_host_x: true
    archlinux-latest:
      image: appimagecrafters/tests-env:archlinux-latest
      command: ./AppRun
      use_host_x: true
    centos-7:
      image: appimagecrafters/tests-env:centos-7
      command: ./AppRun
      use_host_x: true
    ubuntu-xenial:
      image: appimagecrafters/tests-env:ubuntu-xenial
      command: ./AppRun
      use_host_x: true
```

Important note: `use_host_x` instructs the test to run using the host X system, which makes it possible to render GUI elements on the host.

## Troubleshooting
It is safe to remove the `AppDir` and `appimage-build` folders next to recipe file. They may contain cached packages and libraries that prevent successful packaging.

### APT package signing
Apt require package keys to verify them. If this key is not installed it will generate such error:

```
W: GPG error: http://archive.ubuntu.com/ubuntu noble InRelease: The following signatures couldn't be verified because the public key is not available: NO_PUBKEY 871920D1991BC93C
```

To resolve this, add `key_url` to the `AppDir->apt->sorces->source_line` entry.

```yaml
AppDir:
  apt:
    arch: amd64
    sources:
      - sourceline: 'deb [arch=amd64] http://archive.ubuntu.com/ubuntu/ noble main restricted universe multiverse'
        key_url: 'http://keyserver.ubuntu.com/pks/lookup?op=get&search=0x871920D1991BC93C'
``` 