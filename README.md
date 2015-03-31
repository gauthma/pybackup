PyBackup 
===
This script is my solution to the problem of backups. It has two
working modes: it backs up your information either to a LUKS
encrypted external drive, or to some remote location of your
choosing. Information to back up is separated in two components: 

1. Information for which you want multiple integral copies, gzipped.
	 This is usually personal documents that are not very large (for
	 instance, not photos), and that evolve over time. In effect, this
	 implements a rudimentary versioning scheme. For example, a thesis
	 you're working on. But it might also include things like the
	 configuration files in /etc (which might require `sudo` privileges).
	 All this information is stored in a gzipped tarball, named with the
	 current date and timestamp.
	 
2. Information that, due to its volume, you want to keep only a copy,
	 rsync'd with the original. Photos, music or videos, for example.

In the file `backup.json`, in the "dirs" section, you can choose which
folders fit which category. To see the available options, run the
script with the `-h` option. The `directories_excl` is for directories
to be **excluded** from the tarball.

The information to be rsync'd is only sent to the LUKS drive; the
tarball can be stored in the LUKS drive, and/or in the remote (network)
location; in the latter case it will encrypted, the user being prompted
for the password.

For the last scenario (encrypted tarball), and for the user's
convenience a decryption option is also provided (`-d`). Regarding this
options, in the help information (`-h`) it is described as taking
(optionally) more than two arguments: 

~~~ text
optional arguments:
  -d encryptedbackup.tar.gz.gpg [output_dir ...]
~~~

This is due to the way Python parses the argument list ([this
issue](https://stackoverflow.com/questions/23172172/range-for-nargs-in-argparse)
in particular). The `-d` option takes only one mandatory argument (the
name of the encrypted archive), and one optional (the path where to
store the decrypted archive)---by default it is done in the current
directory.

Usage scenarios
---

I usually run the script like so:

~~~ bash
sudo ./pybackup.py
~~~

This will do all three things: create the tar archive, and stored it
both in the LUKS drive and in the remote location; and rsync the big
folders into the LUKS drive.

To do just the local stuff (i.e. rsync and tar to the LUKS drive, but
not to the network), run the script with `-b`. To just copy the tar to
the remote location, use `-r`. To just do rsync use `-R`.

While not strictly necessary, for remote storage, you should configure
your machine so that `scp` can access it without requiring a password,
e.g. with a key to access a hardened account, that is only used for
backup storage.

Install 
---

Just copy the script and config file to any place of your choosing,
`chmod u+x pybackup.py`, customize the config to suit your needs, and
you're done.

The encrypted drive must be identified by its uuid. To determine your
drive's UUID, the output of the following commands might be useful:

```bash
$ mount
$ ls -l /dev/disk/by-uuid
```


Dependencies 
---

It requires cryptsetup, sudo, pv, rsync, gnupg, tar and gzip.

Issues
---

- Works (possibly only) with python 3. 

Notes
---

For instructions on how to created an encrypted LUKS volume, see for
instance, here:
http://www.circuidipity.com/encrypt-external-drive.html
