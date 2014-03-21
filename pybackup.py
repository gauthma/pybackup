#!/usr/bin/env python
 
# pybackup - ease regular encrypted backups
# Copyright (C) 2013 Óscar Pereira

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import os
import subprocess as sp
import json
from time import time
from datetime import date
from getpass import getpass, GetPassWarning
import argparse
import shlex
import subprocess
from shutil import which

# XXX TODO allow backup device to be specified in cmd line!

config = None

# XXX TODO check for all the other dependencies...
def check_deps():
  if which("pv") is None:
    print("pv not found!")
    return False

  return True

def create_tar_archive():
  '''Create tar archive in ~/tmp/tar_archive_name'''
  directories=' '.join([ shellquote(i) for i in config['dirs']['directories'] ])
  root_directories=' '.join([ shellquote(i) for i in config['dirs']['root_directories'] ])
  computer=config['settings']['computer']

  backup_date=date.today().strftime("%Y%b%d")
  tar_archive_name=computer + "-full-" + backup_date +".tar.gz"

  if os.path.exists("~/tmp/" + tar_archive_name):
    return "~/tmp/"+tar_archive_name

  sp.call("sudo tar -cf - " + directories + " " + root_directories + " | pv --wait -s $( 2> /dev/null du -sbc " +
            directories + " " + root_directories + " | tail -1 | awk '{print \
            $1}') | gzip > " + "~/tmp/" + tar_archive_name , shell = True,
            stdout = sp.PIPE )

  return "~/tmp/"+tar_archive_name

def delete_tar_archive(tar_archive_name):
  '''Delete tar archive in ~/tmp/tar_archive_name'''
  sp.call("rm -rf " + "~/tmp/" + tar_archive_name, shell = True)

def backup(tar_archive_path):
  '''Does the backup of tar ONLY. Assumes all drives are mounted (and leaves them like that)'''
  # extract needed info from config file
  computer=config['settings']['computer']
  luks_drive_mount_point=config['settings']['luks_drive_mount_point']
  backup_dir_name=config['settings']['backup_dir_name']
  backup_dir=luks_drive_mount_point + "/" + backup_dir_name
  rsync_directories=[ shellquote(i) for i in config['dirs']['rsync_directories'] ]

  # XXX TODO put pv here to show the copy progress
  sp.call("cp " + tar_archive_path + " " + backup_dir, shell=True);

# MAJOR TODO XXX re-write this in order to ask all the passwords in one go
# (instead of one at a time...)
def remote_backup(tar_archive_path):
  '''Does the remote backup proper. Ignores rsync file/dir list
  remote_backup_path must exist and be writable!'''
  # extract needed info from config file
  backup_dir=config['settings']['remote_backup_tmp_path']
  remote_backup_dir_name=config['settings']['remote_backup_dir_name']
  remote_site=config['settings']['remote_site']
  directories=' '.join([ shellquote(i) for i in config['dirs']['directories'] ])
  root_directories=' '.join([ shellquote(i) for i in config['dirs']['root_directories'] ])

  if (not os.path.exists(os.path.expanduser(backup_dir))):
    print ("Backup tmp path does NOT exist: ", backup_dir, "\nExiting...")
    return

  # now set time/date, and file names
  timestamp=str(round(time()))
  backup_date=date.today().strftime("%Y%b%d")

  # encrypt and scp the result
  try:
    passphrase = "1"
    passphrase1 = "2"
    while passphrase != passphrase1:
      passphrase = getpass(prompt='Please enter encryption passphrase: ')
      passphrase1 = getpass(prompt='Please enter encryption passphrase again: ')
      if passphrase != passphrase1:
        print("Passphrases did NOT match! Try again...")

    print ("Creating encrypted backup archive... (this can take a few minutes)")
    sp.call("echo -n \"" + passphrase + "\" | gpg --symmetric --batch --passphrase-fd 0 --no-tty \
              --cipher-algo aes256 --force-mdc -o " + backup_dir + "/bck-" + timestamp + "-" +
              backup_date + ".tar.gz.gpg " + tar_archive_path, shell=True)
    print ("Transfering encrypted backup archive to remote location...")
    sp.call("scp " + backup_dir + "/bck-" + timestamp + "-" + backup_date +
        ".tar.gz.gpg " + remote_site + ":" + remote_backup_dir_name, shell=True)

    # clean up
    print ("Cleaning up...")
    #sp.call("rm -rf " + backup_dir + "/" + tar_archive_name)
    sp.call("rm -rf " + backup_dir + "/bck-" + timestamp + "-" + backup_date +
        "tar.gz.gpg", shell=True)
    delete_tar_archive()
  except GetPassWarning:
    print("Could not read passphrase. Exiting...")

def decrypt_remote_backup(encrypted_file): # TODO make sure decrypted file is written in current dir, not dir where script is
  '''Assumes that the encrypted file has name like: filename.tar.gz.gpg'''
  try:
    passphrase = getpass(prompt='Please enter decryption passphrase: ')

    print ("Decrypting backup archive... (this can take a few minutes)")
    sp.call("echo -n \"" + passphrase + "\" | gpg --decrypt --batch --passphrase-fd 0 --no-tty \
              --cipher-algo aes256 --force-mdc " + encrypted_file + " > " +
              encrypted_file[:-4], shell=True, stdout=sp.PIPE)
  except GetPassWarning:
    print("Could not read passphrase. Exiting...")

def do_rsync_backup():
  luks_drive_mount_point=config['settings']['luks_drive_mount_point']
  backup_dir_name=config['settings']['backup_dir_name']
  backup_dir=luks_drive_mount_point + "/" + backup_dir_name + "/rsync/"

  rsync_directories=[ shellquote(i) for i in config['dirs']['rsync_directories'] ]
  for folder in rsync_directories:
    # strip trailing slash in folder, if there is one
    # otherwise rsync copies the *contents* of the folder instead of the folder itself
    # WHICH IS PROBLEMATIC BECAUSE OF DELETE
    if folder.endswith('/'): folder = folder[:-1]
    output = sp.check_output("rsync -avz --human-readable --delete-during --exclude=\"*.swp\" "
              + folder + " " + backup_dir, shell=True,)
    print(output)

def parse_config_file():
  from os import path
  script_path=path.dirname(__file__)
  if len(script_path) > 0:
    script_path=script_path+"/"
  try:
    json_data=open(script_path + 'backup.json')
    data=json.load(json_data)
    return data
  except:
    print("Could not read config file:")
    raise
  # useful for debug
  #from pprint import pprint
  #pprint(data)

def shellquote(s):
  '''Handle filenames that need escaping. Borrowed from:
  http://stackoverflow.com/questions/35817/how-to-escape-sp.call-calls-in-python'''
  #return "'" + s.replace("'", "'\\'") + "'"
  return shlex.quote(s)

def mountLuks():
  luksdrive=config['settings']['luksdrive']
  luks_device_name=config['settings']['luks_device_name']
  luks_drive_mount_point=config['settings']['luks_drive_mount_point']

  # check if luks_drive_mount_point does NOT exist: error otherwise
  if (os.path.exists(luks_drive_mount_point)):
    raise RuntimeError("LUKS mount point (" + luks_drive_mount_point + ") exists!\nExiting...")

  open_luks_cmd = "sudo cryptsetup luksOpen " + luksdrive + " " + luks_device_name
  create_luks_mount_point="sudo mkdir -v " + luks_drive_mount_point
  mount_luks_cmd = "sudo mount /dev/mapper/" + luks_device_name + " " + luks_drive_mount_point
  remove_luks_mount_point="sudo rmdir -v " + luks_drive_mount_point

  print("Enter sudo password if necessary!")
  try: # TODO handle this properly! (error capture)
    sp.call(open_luks_cmd, shell=True)
    sp.call(create_luks_mount_point, shell=True)
    sp.call(mount_luks_cmd, shell=True)
  except:
    print("Ups!")
    sp.call(remove_luks_mount_point)

def unmountLuks():
  luks_drive_mount_point=config['settings']['luks_drive_mount_point']
  luks_device_name=config['settings']['luks_device_name']
  remove_luks_mount_point="sudo rmdir -v " + luks_drive_mount_point

  # check that the LUKS mount point really has a LUKS drive mounted
  devnull=open("/dev/null", "w")
  p1=subprocess.Popen(["mount" ], stdout=subprocess.PIPE)
  p2=subprocess.Popen(["grep", luks_drive_mount_point], stdin=p1.stdout, stdout=devnull, stderr=devnull)
  p1.stdout.close()
  p2.communicate()[0]
  if(p2.returncode != 0): # TODO run another grep for /dev/mapper
    print ("LUKS mount point is ", luks_drive_mount_point, "\nBut LUKS drive not mounted there! Exiting...")
    return

  print("Enter sudo password if necessary:")
  sp.call("sudo umount " + luks_drive_mount_point, shell=True)
  sp.call(remove_luks_mount_point, shell=True)
  sp.call("sudo cryptsetup luksClose /dev/mapper/" + luks_device_name, shell=True)

def main():
  if not check_deps():
    exit(-1)

  global config
  config = parse_config_file()

  parser = argparse.ArgumentParser(description='Automate backup process. Run without arguments \
                                   to open LUKS, backup stuff (tar, rsync but NOT remote), and close LUKS.')
  parser.add_argument("-m", "--mount",
                      action="store_true", dest="mountLuks", default=False,
                      help="Only mount LUKS drive, and exit")
  parser.add_argument("-u", "--unmount",
                      action="store_true", dest="unmountLuks", default=False,
                      help="Only UNmount LUKS drive, and exit")
  parser.add_argument("-b", "--backup",
                      action="store_true", dest="do_backup", default=False,
                      help="Mount LUKS drivem, do backup (i.e. tar and rsync AND \
                      remote), unmount.")
  parser.add_argument("-r", "--remote-backup",
                      action="store_true", dest="do_remote_backup", default=False,
                      help="Only do remote backup, (ignores tar and rsync list)")
  parser.add_argument("-R", "--rsync-backup",
                      action="store_true", dest="do_rsync_backup", default=False,
                      help="Only do rsync backup, (ignores tar and remote list)")
  parser.add_argument("-d", "--decrypt-remote-backup",
                      dest="remote_backup_archive_name", default="",
                      help="Decrypt remote backup archive (*.tar.gz.gpg)")

  args = parser.parse_args()

  if args.mountLuks:
    mountLuks()
  elif args.unmountLuks:
    unmountLuks()
  elif args.do_backup:
    mountLuks()
    tar_archive_path = create_tar_archive()
    remote_backup(tar_archive_path)
    backup(tar_archive_path)
    delete_tar_archive(tar_archive_path)
    do_rsync_backup()
    unmountLuks()
  elif args.do_remote_backup:
    tar_archive_path = create_tar_archive()
    remote_backup(tar_archive_path)
    delete_tar_archive(tar_archive_path)
  elif args.do_rsync_backup:
    mountLuks()
    do_rsync_backup()
    unmountLuks()
  elif args.remote_backup_archive_name:
    decrypt_remote_backup(args.remote_backup_archive_name)
  else:
    mountLuks()
    tar_archive_path = create_tar_archive()
    backup(tar_archive_path)
    delete_tar_archive(tar_archive_path)
    do_rsync_backup()

    unmountLuks()

if __name__ == "__main__":
  main()
