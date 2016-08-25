PyBackup 
===

This script is my solution to the problem of backups. It backs up your
information to a LUKS encrypted external drive. Information to back up
is separated in two components:

1. Information for which you want multiple integral copies,
	 gzipped. This is usually personal documents that are not very
	 large (for instance, not photos), and that evolve over time. In
	 effect, this implements a rudimentary versioning scheme. For
	 example, a thesis you're working on. But it might also include
	 things like the configuration files in /etc (which might require
	 `sudo` privileges). All this information is stored in a gzipped
	 tarball, named with the current date and timestamp.
2. Information that, due to its volume, you want to keep only a
	 copy, rsync'd with the original. Photos, music, videos, for
	 example.

In the file `backup.json`, in the `dirs` section, you can choose which
folders fit which category. Too see the available options, run the
script with the `-h` option. The `directories_excl` is for directories
to be **excluded** from the tarball.

Dependencies 
---

It requires `cryptsetup`, `sudo`, `pv`, `rsync`, `tar` and `gzip`.
Except for [`pv`](https://www.ivarch.com/programs/pv.shtml), they should
all be provided by a recent GNU/Linux installation. There is on-going
work to provide checks for all the needed dependencies.

It also requires the `python` language, version 3.


The LUKS what?
----

**LUKS** (*Linux Unified Key Setup*) is a disk encryption specification.
It uses the `cryptsetup` command line tool to interface with the
relevant kernel submodule (`dm-crypt`).

The first step to format your drive with LUKS is find its device label
(e.g. `sdb`, `sdc`, etc.). The `lsblk` might be helpful for this task.
Henceforth the device label is assumed to be `sdX`. If you want to use a
partition (instead of the whole disk), that is possible too---just use
the label followed by the partition number, e.g. `sdX3`. Here we use the
entire disk, which will contain only one partition, `sdX1` (you always
need to have at least one partition...). But whether you use an entire
drive or only a partition, *please ensure it is **unmounted** *.

The next (optional) step is to overwrite the device with zeros. For even
more ~~paranoia~~ security, use `/dev/random` instead of `/dev/zero`
below (but beware it will be *much* slower):

~~~ text
# dd bs=4M if=/dev/zero of=/dev/sdX
~~~

***THIS WILL WIPEOUT EXISTING DATA*** on `/dev/sdX`, so please be sure
you type the correct device label. Note the line begins with an hash
(`#`) rather than a `$`, which means it is in privileged mode
(`su/sudo`).

If you `dd`-ied your entire disk, your partitions have been deleted, so
please format it as you see fit (`cfdisk` is an easy to use---albeit
command line---tool to do so).

The next step is the first where `cryptsetup` is actually used. We
create the encrypted container in `sdX1`, and open it so as to be able
to write it.

~~~ text
# cryptsetup luksFormat /dev/sdX1
# cryptsetup luksOpen   /dev/sdX1 pybackup_drive
~~~

The decrypted drive is now available `/dev/mapper/pybackup_drive`. All
that is left is to create a filesystem and close the container.

~~~ text
# mkfs.ext4 -L luks_backup /dev/sdX1
~~~

The `-L` is for adding a label to the decrypted volume; this is useful
when browsing through it with a graphical file explorer. It is not
mandatory.

Now just close the LUKS container and we are done. The `umount` is just
required if you mounted the drive.

~~~ text
# umount /dev/mapper/pybackup_drive
# cryptsetup luksClose /dev/mapper/pybackup_drive
~~~

This overview is adapted from
[here](http://www.circuidipity.com/encrypt-external-drive.html).

External Drive
---

With the `-b` option, the script mounts/decrypts the drive, backs up
both tar and rsync information, and unmounts/encrypts back the drive.

The files or folders to be backed up are read from a config file named
`backup.json`, which must reside in the same place has the python
script. Here's the process:

- create a tarball with the files/folders in dirs->directories and 
	dirs->root_directories and save it to the settings->backup_dir_name 
	folder in the encrypted drive 
- rsync the contents of the folders in dirs->rsync_directories to
	equally named folders in settings->backup_dir_name/rsync 

The `-R` can be used, to skip creating the tar file, and just do rsync. 

The `-m/-u` mount (and decrypt) and unmount (and encrypt) the LUKS
drive, respectively. Note that this is automatically done for `-b` and
`-R` options; the `-m/-u` options are convenient to *recover* the actual
backup information.

The encrypted drive or partition must be identified by its UUID. To
determine it, the output of the following commands might be useful:

```bash
$ mount
$ ls -l /dev/disk/by-uuid
```

`cfdisk` also provides this information.

Install & Configuration
---

Just copy the script and config file to any place of your choosing,
customize the latter to suit your needs, and you're done.

As for configuration, the `dirs` part is straightforward: just put the
names of the folders you want backed up (`~` is expanded to your home
folder).

About the `settings` part, *only the `luksUUID` is mandatory*; the rest
are optional, and default to what is stated in a comment after the
setting. Note that this means the JSON below is invalid, for its spec
does not allow comments. Use the provided skeleton to begin your
configuration.

~~~ json
{
	"settings"          : {
		"computer"        : "mypc"                                 , # hostname, not FQDN. If omitted, is detected by python
		"user"            : "myself"                               , # username of user running script. If omitted, is detected by python
		"tmp_path"        : "~/tmp/backups"                        , # path where tarball and LUKS mount point are created; defaults to ~
		"backup_dir_name" : "backups"                              , # path inside backup device where to store tar and rsync; defaults to root of device
		"luksUUID"        : "00000000-0000-0000-0000-000000000000" , # see previous section
	}                                                            ,

	"dirs"		: {
		"rsync_directories"	: [ "~/someFolder1"  ,
                        "~/someFolder2" ,
                        "~/someFolder3" ] ,

		"root_directories"	: [ "/etc" ] ,

		"directories"				: [ "~/someFolder4" ,
                        "~/someFile1" ,
                        "~/someFile2" ]
	}
}
~~~

Issues
---

- Tested with (arch) linux (and python 3). In other platforms/versions,
	*caveat emptor*.

Notes
---

To ease hacking (or just to try this LUKS stuff out), you can create a
dummy LUKS container on a regular file. Here's how (adapt as needed):

~~~ text
--> make sure size is enough for you data
# ff=/dev/zero bs=1M count=500 of=foo.img

# cryptsetup luksFormat foo.img

# cryptsetup luksOpen foo.img test

# ls /dev/mapper/test

# mkfs.ext4 /dev/mapper/test

# mkdir bar

# mount /dev/mapper/test bar/

# chown -R yourusername bar

# umount bar
# cryptsetup luksClose test
~~~
