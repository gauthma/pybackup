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

External Drive
---

With the `-b` option, the script mounts/decrypts the drive, backs up
both tar and rsync information, and unmounts/encrypts back the drive.

The files or folders to be backed up are read from a config file named
`backup.json`, which must reside in the same place has the python
script. Here's the process:

- create a tarball with the files/folders in dirs->directories and 
	dirs->root_directories and save it the settings->backup_dir_name 
	in the encrypted drive 
- rsync the contents of the folders in dirs->rsync_directories to
	equally named folders in settings->backup_dir_name/rsync 

The `-R` can be used, to skip creating the tar file, and just do rsync. 

The `-m/-u` mount (and decrypt) and unmount (and encrypt) the LUKS
drive, respectively. Note that this is automatically done for `-b` and
`-R` options; the `-m/-u` options are convenient to *recover* the actual
backup information.

The encrypted drive must be identified by its UUID. To determine your
drive's UUID, the output of the following commands might be useful:

```bash
$ mount
$ ls -l /dev/disk/by-uuid
```

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

Dependencies 
---

It requires dm_crypt, sudo, pv, rsync, tar and gzip. There is
on-going work to provide checks for all the needed dependencies.

Issues
---

- Tested with (arch) linux and python 3. In other platforms, *caveat
	emptor*.

Notes
---

For instructions on how to created an encrypted LUKS volume, see for
instance, here:
http://www.circuidipity.com/encrypt-external-drive.html
