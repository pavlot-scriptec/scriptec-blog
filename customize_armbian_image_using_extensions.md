# Customize Armbian image using extensions

## Armbian extensions

The extensions framework allows developers to enhance the Armbian build system by adding specific features without modifying the core system.

This is Bash script framework that works based on function naming conventions. Extension is a simple (or complex) Bash script placed in `userpatches/extensions` folder. Extension script should contain only function definitions. This script should not contain any code which is executed outside that functions. The same rule applies to any script sourced by extension script.

To enable extension pass parameter `ENABLE_EXTENSIONS=<comma separated list of enabled extensions>` to armbian compile script

Extension could be placed inside a separate folder inside `userpatches/extensions`. This is useful to split and organize extensions. Folder name does not matter, only the extension file name matters - `ENABLE_EXTENSIONS=` will be looking for the given filename inside `userpatches/extensions`  

## Hook functions

The key concept of extension scripting is **extension_methods** - functions that follow a special naming pattern: `hook_name__extension_method_name`.
`hook_name` - one of the names described on [Hooks](https://docs.armbian.com/Developer-Guide_Extensions-Hooks/) page. It defines at what stage of the build process extension function will be executed. E.g. if some actions should be performed when the image is ready and about to be unmounted `pre_umount_final_image` hook should be used.

After `hook_name` should be two underscores. This is important as function name parser looks for this token to identify the script method as extension method

And the last part - `extension_method_name`. Some descriptive name that explain what your method is doing.

## Ordering

After extension methods are parsed, each method whose name is not started with `xxx_` (`x` means any digit) will receive `500_` prefix. This allows to define the order of execution. 

Let's see example. We have 3 extensions, each has some code to be executed with `post_customize_image` hook.

Option 1 each extension defines its methods without any prefixes:

extension-1.sh
``` Bash
function post_customize_image__extension_1_method()
 {
 }
```

extension-2.sh

``` Bash
function post_customize_image__extension_2_method()
 {
 }
```
extension-3.sh
``` Bash
function post_customize_image__extension_3_method()
 {
 }
```

After parsing each method will be prepended with `500_` prefix and they will be executed in order 1, 2, 3.

But if extension3 needs to be executed before others, a developer can define it as:
``` Bash
function post_customize_image__100_extension_3_method()
 {
 }
```
and in this case order of execution will be 3, 1, 2

## Install TFT drivers with extensions

Practical example of how extensions could be used: Waveshare produces [3.5" TFT's](https://www.waveshare.com/wiki/3.5inch_RPi_LCD_(A)) for RaspberryPi. They work with fbtft driver already present in the kernel, but require some configuration. 

The following steps are required to make them work:

1. Overlays should be installed to `/boot/overlays` folder
2. `config.txt` must be altered to enable SPI and configure proper overlay

So let's do it.

### Prepare build environment

Clone armbian project `git clone --depth=1 --branch=main https://github.com/armbian/build`

Compile minimal image it for RaspberryPi 4 to make sure it is built:
``` Bash
cd build
./compile.sh BOARD=rpi4b BRANCH=current RELEASE=bookworm BUILD_MINIMAL=yes BUILD_DESKTOP=no KERNEL_CONFIGURE=prebuilt 
```

### Create extension

Inside the build dir create `userpatches/extensions` folder
``` Bash
mkdir -p userpatches/extensions
```
Make a new extension folder:
``` Bash
mkdir -p userpatches/extensions/install-waveshare-35-tft
touch userpatches/extensions/install-waveshare-35-tft/install-waveshare-35-tft.sh
mkdir -p userpatches/extensions/install-waveshare-35-tft/overlays
```

#### Overlay files

Before continuing overlay files must be downloaded from Waveshare [repository](https://github.com/waveshare/LCD-show)

These overlay files should be placed to the extensions `overlays` folder.

Go outside armbian build directory, clone it, and copy the required files to the extension overlays folder:
``` Bash
# Assume we are in Armbian build folder now
cd ..
git clone https://github.com/waveshare/LCD-show.git
cd LCD-show/
cp LCD-show/waveshare35a-overlay.dtb build/userpatches/extensions/install-waveshare-35-tft/overlays/waveshare35a.dtbo
cp LCD-show/waveshare35b-overlay.dtb build/userpatches/extensions/install-waveshare-35-tft/overlays/waveshare35b.dtbo
cp LCD-show/waveshare35b-v2-overlay.dtb build/userpatches/extensions/install-waveshare-35-tft/overlays/waveshare35b-v2.dtbo

```

#### Install overlays from the extension and update the config file

Now let's add some code, go back to Armbian build directory, and open `userpatches/extensions/install-waveshare-35-tft/install-waveshare-35-tft.sh` with a text editor.

``` Bash
#!/bin/bash

function pre_umount_final_image__install_overlays() {
    display_alert "Installing Waveshare 3.5 TFT overlays" "info"
    run_host_command_logged cp -v "${EXTENSION_DIR}/overlays/*.dtbo" "${MOUNT}/boot/firmware/overlays"
}

# ---------------------------------------------------------------------------------------------------

function pre_umount_final_image__550_update_config() {
    display_alert "Update config for Waveshare 3.5 TFT" "info"
    FILENAME="${MOUNT}/boot/firmware/config.txt"
    printf "\n# ${BASH_SOURCE[0]}" >>"${FILENAME}"
    printf "\n# TFT display config" >>"${FILENAME}"
    printf "\ndtparam=spi=on" >>"${FILENAME}"
    printf "\ndtoverlay=waveshare35a,speed=20000000,rotate=270\n" >>"${FILENAME}"
    printf "\nignore_lcd=0" >>"${FILENAME}" >>"${FILENAME}"

}
```
The function `pre_umount_final_image__install_overlays` is straightforward:  Display message and copy overlay files from the extension folder to the image

Function `pre_umount_final_image__550_update_config` updates config.txt on the image. It has to be executed with order `550_` because config.txt file is created by RPi extension somewhere at order `500_`. So to guarantee that our extension will modify the existing file, we have to call it after all `500` routines are complete. In general even `501_` should be enough, `550_` just looks better and allow to insert of something between `500_` and `550_` 

Now time to build image with this extension enabled:
``` Bash
./compile.sh BOARD=rpi4b BRANCH=current RELEASE=bookworm BUILD_MINIMAL=yes BUILD_DESKTOP=no KERNEL_CONFIGURE=prebuilt ENABLE_EXTENSIONS=install-waveshare-35-tft
```

### Extension parameters

The function `pre_umount_final_image__550_update_config` configures the target image to use Waveshare 3.5 TFT display version "A". But we have also overlays for version "B" and "B-v2".

We can change the line `printf "\ndtoverlay=waveshare35a,speed=20000000,rotate=270\n" >>"${FILENAME}"` to use another overlay, but also it is possible to use variables to change this parameter (or any other).

First `pre_umount_final_image__550_update_config` needs to be modified:

``` Bash
# ---------------------------------------------------------------------------------------------------
# Variables:
#   EXT_INSTALL_WAVESHARE_35_TFT_OVERLAY - name of the overlay to be used in config.txt
function pre_umount_final_image__550_update_config() {
    if [[ -z "${EXT_INSTALL_WAVESHARE_35_TFT_OVERLAY}" ]]; then
        EXT_INSTALL_WAVESHARE_35_TFT_OVERLAY="waveshare35a"
    fi
    
    display_alert "Update config for Waveshare 3.5 TFT, overlay ${EXT_INSTALL_WAVESHARE_35_TFT_OVERLAY}" "info"
    FILENAME="${MOUNT}/boot/firmware/config.txt"
    printf "\n# ${BASH_SOURCE[0]}" >>"${FILENAME}"
    printf "\n# TFT display config" >>"${FILENAME}"
    printf "\ndtparam=spi=on" >>"${FILENAME}"
    printf "\ndtoverlay=${EXT_INSTALL_WAVESHARE_35_TFT_OVERLAY},speed=20000000,rotate=270\n" >>"${FILENAME}"
    printf "\nignore_lcd=0" >>"${FILENAME}" >>"${FILENAME}"

}
```
Variable `EXT_INSTALL_WAVESHARE_35_TFT_OVERLAY` was added. By default it is set to "waveshare35a" but now it is possible to overwrite it with commandline parameters. E.g. if "B" version is required, compilation should be started like this:

``` Bash
./compile.sh BOARD=rpi4b BRANCH=current RELEASE=bookworm BUILD_MINIMAL=yes BUILD_DESKTOP=no KERNEL_CONFIGURE=prebuilt ENABLE_EXTENSIONS=install-waveshare-35-tft EXT_INSTALL_WAVESHARE_35_TFT_OVERLAY="waveshare35b-v2"
```

## Links

Code from this article is placed on [GitHub](https://github.com/pavlot-scriptec/scriptec-armbian-ext-waveshare-35tft)
