PyBackup 
===
This script is my solution to the problem of backups. It has two
working modes: it backs up your information either to a LUKS
encrypted external drive, or to some remote location of your
choosing. Information to back up is separated in three components: 

1. Information for which you want multiple integral copies,
	 gzipped. This is usually personal documents that are not very
	 large (for instance, not photos), and that evolves over time.
	 For example, a thesis you're working on. But it might also
	 include things like the configuration files in /etc (which
	 might require `sudo` privileges). All this information is
	 stored in a gzipped tarball, named with the current date and
	 timestamp.
2. Information that, due to its volume, you want to keep only a
	 copy, rscynced with the original. Photos, music, videos, for
	 example.

In the file backup.json, in the "dirs" section, you can choose which folders
fit which category. Too see the available options, run the script
with the `-h` option.

External Drive
---
In the external drive scenario, it mounts/decrypts the drive, backs
up what has to be backed up, and unmounts/encrypts the drive. The
files or folders to be backed up are read from a config file named
`backup.json`, which must reside in the same place has the python
script. All the three types of information mentioned above are
backed up. To use this mode, run the script with no command line
options. Here's the process:

 - create a tarball with the files/folders in dirs/directories and
	 save it the settings/backup_dir_name in the encrypted drive 
 - create a tarball with the files/folders in dirs/root_directories,
	 and idem.
 - rsync the contents of the folders in dirs/rsync_directories to
	 equally named folders in settings/backup_dir_name 

Remote Network Storage
---
The second scenario only backs up types 1. and 2. of information.
Folders to be rsynced are NOT backed up. The is done invoking the
script with the `-r` option. Process outline:

 - create a tarball with the files and folders to back up, and save
	 it in settings:remote_backup_tmp_path. 
 - encrypt that tarball using GnuPG with symmetric encryption, and a
	 user supplied pass-phrase. This creates an archive in the same
	 location as above, with the extension *.tar.gz.gpg. 
 - scp the encrypted archive to settings:remote_backup_dir_name in
	 the machine settings:remote_site. Due note that this last setting
	 must be something that can appended to "scp " and connect
	 successfully. 
 - remove (clean up) the files created on the local machine.

For your convenience, the capability of decrypting the tar.gz.gpg is
also provided: just call the script with "-d
archive_name.tar.gz.gpg". You'll be prompted for the password, and
the decrypted version archive_name.tar.gz will be produced in the
current folder. 

Install 
---
Just copy the script and config file to any place of your choosing,
customize the latter to suit your needs, and you're done.

Dependencies 
---
It requires dm_crypt, sudo, pv, rsync, gnupg, tar and gzip. There is
on-going work to provide checks for all the needed dependencies.

Issues
---
 - Works (possibly only) with python 3. 

Notes
---
For instructions on how to created an encrypted LUKS volume, see for
instance, here:
http://www.circuidipity.com/encrypt-external-drive.html
