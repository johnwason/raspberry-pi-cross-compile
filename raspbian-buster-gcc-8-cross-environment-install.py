#!/usr/bin/python3

# Install a gcc-8 cross environment using the
# built in gcc-8-arm-linux-gnueabihf toolchain in Debian amd64
#
# This is implemented using the following steps:
# 1. Install gcc-8-arm-linux-gnueabihf and g++-8-arm-linux-gnueabihf packages
# 2. Install qemu-user-static, binfmt-support, debootstrap, and 
#    schroot to create a chroot environment
# 3. Install a raspbian buster chroot system at /var/chroot/raspbian_buster_armhf
#    Thanks to qemu-user-static and binfmt-support, this environment
#    can be emulated transparently and used as a normal chroot
# 4. Create a gcc "specs" file that overrides the default flags
#    passed to subtools such as ld. By default, the compiler always
#    links for armv7. This is due to the standard object files
#    that are used to initialize and shut down a binary. Override
#    these flags using the "specs" files.
# 5. Replace several so absolute links in chroot with relative links
# 6. Create a cmake toolchain file with the required flags etc to
#    accomplish the cross compilation. These flags configure the
#    compiler to produce armv6 instructions, and set a number
#    of obscure preprocessor defines to match the raspbian
#    compiler
#
# The result of these steps is a toolchain file located at
# /opt/toolchains/gcc-8-armv6.cmake .  Programs can be
# run in the chroot using the command format:
#
#   schroot -c raspbian_buster_armhf -- my_command
#
# This script requires a working "sudo" command
#
#   readelf -a -W app  | grep CPU
# to check CPU
#
# References:
#
#  https://stackoverflow.com/questions/28904902/how-do-i-change-gccs-default-search-directory-for-crti-o
#  https://gcc.gnu.org/onlinedocs/gcc/Spec-Files.html
#  https://jod.al/2015/03/08/building-arm-debs-with-pbuilder/
#  https://askubuntu.com/questions/36211/undefined-reference-error-dl-stack-flags-with-gcc-and-pthreads
#  https://stackoverflow.com/questions/7493620/inhibit-default-library-paths-with-gcc
#  https://transang.me/library-path-in-gcc/
#  https://raspberrypi.stackexchange.com/questions/2046/which-cpu-flags-are-suitable-for-gcc-on-raspberry-pi
#  
# John Wason, Ph.D., Wason Technology, 2021

import subprocess
import re
from pathlib import Path
import os
import pwd

def c(cmd):
    subprocess.check_call(cmd, shell=True)

def getuser():
    return pwd.getpwuid(os.geteuid()).pw_name

def install_host_deps():
    c("sudo apt update")
    c("sudo apt install -y gcc-8-arm-linux-gnueabihf g++-8-arm-linux-gnueabihf cmake build-essential" \
      "qemu-user-static binfmt-support debootstrap schroot" )

def make_dirs():
    c("sudo mkdir -p /opt/toolchains")
    c("sudo mkdir -p /var/chroot")

def install_chroot():

    if not Path("/usr/share/keyrings/raspbian-archive-keyring.gpg").is_file():
        c("cd /tmp && wget http://archive.raspbian.org/raspbian/pool/main/r/raspbian-archive-keyring/raspbian-archive-keyring_20120528.2_all.deb")
        c("sudo dpkg -i /tmp/raspbian-archive-keyring_20120528.2_all.deb")

    if not Path("/var/chroot/raspbian_buster_armhf/bin/bash").exists():
        c("sudo debootstrap --arch armhf --foreign --keyring=/usr/share/keyrings/raspbian-archive-keyring.gpg buster /var/chroot/raspbian_buster_armhf http://ftp.acc.umu.se/mirror/raspbian/raspbian/")
        c("sudo cp /usr/bin/qemu-arm* /var/chroot/raspbian_buster_armhf/usr/bin")
        c("sudo chroot /var/chroot/raspbian_buster_armhf /debootstrap/debootstrap --second-stage")

    username= getuser()
    schroot_config2 = schroot_config.replace("{user}", username)
    with open("/tmp/raspbian_buster_armhf", "w") as f:
        f.write(schroot_config2)
    c("sudo chown root:root /tmp/raspbian_buster_armhf")
    c("sudo mv /tmp/raspbian_buster_armhf /etc/schroot/chroot.d/")

    c("sudo schroot -c raspbian_buster_armhf -- apt-get update")
    c("sudo schroot -c raspbian_buster_armhf -- apt-get install -y build-essential g++ gcc cmake")

def write_gcc_specs():
    proc = subprocess.Popen(["/usr/bin/arm-linux-gnueabihf-g++-8", "-dumpspecs"], stdout=subprocess.PIPE)

    specs = proc.stdout.read().decode("utf-8")
    specs = specs.replace("%D",ld_search_paths)

    def replace_with_path(m):
        
        obj = m.group()
        try:
            obj_absolute = str(next(Path("/var/chroot/raspbian_buster_armhf").rglob(obj)))
        except StopIteration:
            return obj
        print("specs replacing: " + m.group() + " found absolute " + obj_absolute)
        return obj_absolute

    specs = re.sub(r"\w+\.o", replace_with_path, specs)

    with open("/tmp/gcc-8-armv6-specs.txt", "w") as f:
        f.write(specs)

    c("sudo mv /tmp/gcc-8-armv6-specs.txt /opt/toolchains/")

def write_cmake_toolchain():
    with open("/tmp/gcc-8-armv6.cmake","w") as f:
        f.write(cmake_toolchain_text)
    c("sudo mv /tmp/gcc-8-armv6.cmake /opt/toolchains/")

def fix_absolute_links():
    for path in Path("/var/chroot/raspbian_buster_armhf/lib").rglob("*"):
        if not path.is_symlink():
            continue

        m = re.match(r".*(?:(?:\.so(?:\.\d+)?)|(?:\.a))$", path.name)
        if m is None:
            continue
        link_target = Path(os.readlink(path))
        if not link_target.is_absolute():
            continue
        rel_link_target = "../"*(len(Path(str(path).replace("/var/chroot/raspbian_buster_armhf","")).parent.parts)-1) + str(link_target).lstrip("/")
        print("replace " + str(path) + " -> " + str(link_target) + " with relative link " + rel_link_target)

        print(f"cd {path.parent} && sudo ln -fs {rel_link_target} {path.name}")
        c(f"cd {path.parent} && sudo ln -fs {rel_link_target} {path.name}")

def main():
    install_host_deps()
    install_chroot()
    make_dirs()
    write_cmake_toolchain()
    write_gcc_specs()
    fix_absolute_links()

cmake_toolchain_text= \
"""
set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR arm)

set(CMAKE_SYSROOT /var/chroot/raspbian_buster_armhf)

set(CMAKE_C_COMPILER /usr/bin/arm-linux-gnueabihf-gcc-8)
set(CMAKE_CXX_COMPILER /usr/bin/arm-linux-gnueabihf-g++-8)
set(CMAKE_C_FLAGS " -mcpu=arm1176jzf-s -mtune=arm1176jzf-s  -isystem=/var/chroot/raspbian_buster_armhf  -march=armv6 -mfpu=vfp -mfloat-abi=hard -marm -D__GCC_HAVE_SYNC_COMPARE_AND_SWAP_1 -D__GCC_HAVE_SYNC_COMPARE_AND_SWAP_2 -D__GCC_HAVE_SYNC_COMPARE_AND_SWAP_8 -D__ARM_FEATURE_LDREX=4 -D__GCC_ATOMIC_BOOL_LOCK_FREE=1 -D__GCC_ATOMIC_CHAR_LOCK_FREE=1 -D__GCC_ATOMIC_CHAR16_T_LOCK_FREE=1 -D__GCC_ATOMIC_LLONG_LOCK_FREE=1 -D__GCC_ATOMIC_SHORT_LOCK_FREE=1 -D__pic__ -D__PIC__ -D__pie__ -D__PIE__ -Wl,--sysroot=/var/chroot/raspbian_buster_armhf -specs=/opt/toolchains/gcc-8-armv6-specs.txt  " )
set(CMAKE_CXX_FLAGS "-mcpu=arm1176jzf-s -mtune=arm1176jzf-s  -isystem=/var/chroot/raspbian_buster_armhf  -march=armv6 -mfpu=vfp -mfloat-abi=hard -marm -D__GCC_HAVE_SYNC_COMPARE_AND_SWAP_1 -D__GCC_HAVE_SYNC_COMPARE_AND_SWAP_2 -D__GCC_HAVE_SYNC_COMPARE_AND_SWAP_8 -D__ARM_FEATURE_LDREX=4 -D__GCC_ATOMIC_BOOL_LOCK_FREE=1 -D__GCC_ATOMIC_CHAR_LOCK_FREE=1 -D__GCC_ATOMIC_CHAR16_T_LOCK_FREE=1 -D__GCC_ATOMIC_LLONG_LOCK_FREE=1 -D__GCC_ATOMIC_SHORT_LOCK_FREE=1 -D__pic__ -D__PIC__ -D__pie__ -D__PIE__  -Wl,--sysroot=/var/chroot/raspbian_buster_armhf -specs=/opt/toolchains/gcc-8-armv6-specs.txt " )


set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)


"""

ld_search_paths = "-L/var/chroot/raspbian_buster_armhf/lib -L/var/chroot/raspbian_buster_armhf/lib/arm-linux-gnueabihf " \
    "-L/var/chroot/raspbian_buster_armhf/usr/lib -L/var/chroot/raspbian_buster_armhf/usr/lib/arm-linux-gnueabihf " \
    "-L/var/chroot/raspbian_buster_armhf/usr/lib/arm-linux-gnueabihf "\
    "-L/var/chroot/raspbian_buster_armhf/usr/lib/gcc/arm-linux-gnueabihf/8"

schroot_config = \
"""
[raspbian_buster_armhf]
description=Raspbian Buster armhf chroot
type=directory
directory=/var/chroot/raspbian_buster_armhf
users={user}
root-groups=root,{user}
"""

if __name__ == "__main__":
    main()