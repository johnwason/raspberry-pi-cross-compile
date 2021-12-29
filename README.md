
# raspbian-buster-gcc-8-cross-environment-install.py

Install a gcc-8 cross environment using the
built in gcc-8-arm-linux-gnueabihf toolchain in Debian amd64

This is implemented using the following steps:
1. Install gcc-8-arm-linux-gnueabihf and g++-8-arm-linux-gnueabihf packages
2. Install qemu-user-static, binfmt-support, debootstrap, and 
   schroot to create a chroot environment
3. Install a raspbian buster chroot system at /var/chroot/raspbian_buster_armhf
   Thanks to qemu-user-static and binfmt-support, this environment
   can be emulated transparently and used as a normal chroot
4. Create a gcc "specs" file that overrides the default flags
   passed to subtools such as ld. By default, the compiler always
   links for armv7. This is due to the standard object files
   that are used to initialize and shut down a binary. Override
   these flags using the "specs" files.
5. Replace several so absolute links in chroot with relative links
6. Create a cmake toolchain file with the required flags etc to
   accomplish the cross compilation. These flags configure the
   compiler to produce armv6 instructions, and set a number
   of obscure preprocessor defines to match the raspbian
   compiler

The result of these steps is a toolchain file located at
/opt/toolchains/gcc-8-armv6.cmake .  Programs can be
run in the chroot using the command format:

  schroot -c raspbian_buster_armhf -- my_command

This script requires a working "sudo" command

  readelf -a -W app  | grep CPU
to check CPU

References:

 https://stackoverflow.com/questions/28904902/how-do-i-change-gccs-default-search-directory-for-crti-o
 https://gcc.gnu.org/onlinedocs/gcc/Spec-Files.html
 https://jod.al/2015/03/08/building-arm-debs-with-pbuilder/
 https://askubuntu.com/questions/36211/undefined-reference-error-dl-stack-flags-with-gcc-and-pthreads
 https://stackoverflow.com/questions/7493620/inhibit-default-library-paths-with-gcc
 https://transang.me/library-path-in-gcc/
 https://raspberrypi.stackexchange.com/questions/2046/which-cpu-flags-are-suitable-for-gcc-on-raspberry-pi
 
John Wason, Ph.D., Wason Technology, 2021