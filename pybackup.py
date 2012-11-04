#!/usr/bin/env python

import os
import json
from time import time
from datetime import date
from getpass import getpass, GetPassWarning
import argparse

config = ""

def backup(config):
  '''Does the backup proper. Assumes all drives are mounted (and leaves them like that)'''
  # extract needed info from config file
  computer=config['settings']['computer']
  luks_drive_mount_point=config['settings']['luks_drive_mount_point']
  backup_dir_name=config['settings']['backup_dir_name']
  backup_dir=luks_drive_mount_point + "/" + backup_dir_name
  directories=' '.join([ shellquote(i) for i in config['dirs']['directories'] ])
  root_directories=' '.join([ shellquote(i) for i in config['dirs']['root_directories'] ])
  rsync_directories=[ shellquote(i) for i in config['dirs']['rsync_directories'] ]

  # now set time/date, and file names
  timestamp=str(round(time()))
  backup_date=date.today().strftime("%Y%b%d")
  tar_archive_name=computer + "-" + timestamp + "-full-" + backup_date +".tar.gz"
  root_tar_archive_name=computer + "-ROOTCFG-" + timestamp + "-" + backup_date +".tar.gz"

  os.system("sudo tar -cf - " + directories + " " + root_directories + " | pv --wait -s $( 2> /dev/null du -sbc " +
            directories + " " + root_directories + " | tail -1 | awk '{print $1}') | gzip > " + backup_dir + "/" + tar_archive_name )

  do_rsync_backup()

def remote_backup():
  '''Does the remote backup proper. Ignores rsync file/dir list
     remote_backup_path must exist and be writable!'''
  # extract needed info from config file
  computer=config['settings']['computer']
  backup_dir=config['settings']['remote_backup_tmp_path']
  remote_backup_dir_name=config['settings']['remote_backup_dir_name']
  remote_site=config['settings']['remote_site']
  directories=' '.join([ shellquote(i) for i in config['dirs']['directories'] ])
  root_directories=' '.join([ shellquote(i) for i in config['dirs']['root_directories'] ])

  # now set time/date, and file names
  timestamp=str(round(time()))
  backup_date=date.today().strftime("%Y%b%d")
  tar_archive_name=computer + "-" + timestamp + "-full-" + backup_date +".tar.gz"
  root_tar_archive_name=computer + "-ROOTCFG-" + timestamp + "-" + backup_date +".tar.gz"

  os.system("sudo tar -cf - " + directories + " " + root_directories + " | pv --wait -s $( 2> /dev/null du -sbc " +
            directories + " " + root_directories + " | tail -1 | awk '{print $1}') | gzip > " + backup_dir + "/" + tar_archive_name )

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
    os.system("echo -n \"" + passphrase + "\" | gpg --symmetric --batch --passphrase-fd 0 --no-tty \
              --cipher-algo aes256 --force-mdc -o " + backup_dir + "/bck-" + timestamp + "-" +
              backup_date + "tar.gz.gpg " + backup_dir + "/" + tar_archive_name)
    print ("Transfering encrypted backup archive to remote location...")
    os.system("scp " + backup_dir + "/bck-" + timestamp + "-" + backup_date + "tar.gz.gpg " + remote_site + ":" + remote_backup_dir_name)

    # clean up
    print ("Cleaning up...")
    os.system("rm -rf " + backup_dir + "/" + tar_archive_name)
    os.system("rm -rf " + backup_dir + "/bck-" + timestamp + "-" + backup_date + ".gpg")
  except GetPassWarning:
    print("Could not read passphrase. Exiting...")

def decrypt_remote_backup(encrypted_file): # TODO make sure decrypted file is written in current dir, not dir where script is
  '''Assumes that the encrypted file has name like: filename.tar.gz.gpg'''
  try:
    passphrase = getpass(prompt='Please enter decryption passphrase: ')

    print ("Decrypting backup archive... (this can take a few minutes)")
    os.system("echo -n \"" + passphrase + "\" | gpg --decrypt --batch --passphrase-fd 0 --no-tty \
              --cipher-algo aes256 --force-mdc " + encrypted_file + " > " + encrypted_file[:-4] )
  except GetPassWarning:
    print("Could not read passphrase. Exiting...")

def do_rsync_backup():
  luks_drive_mount_point=config['settings']['luks_drive_mount_point']
  backup_dir_name=config['settings']['backup_dir_name']
  backup_dir=luks_drive_mount_point + "/" + backup_dir_name

  rsync_directories=[ shellquote(i) for i in config['dirs']['rsync_directories'] ]
  for folder in rsync_directories:
    os.system("rsync -avz --human-readable --delete-before --exclude=\"*.swp\" "
              + folder + " " + backup_dir)

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
  http://stackoverflow.com/questions/35817/how-to-escape-os-system-calls-in-python'''
  return "'" + s.replace("'", "'\\'") + "'"

def mountLuks(config):
  luksdrive=config['settings']['luksdrive']
  luks_device_name=config['settings']['luks_device_name']
  luks_drive_mount_point=config['settings']['luks_drive_mount_point']

  open_luks_cmd = "sudo cryptsetup luksOpen " + luksdrive + " " + luks_device_name
  create_luks_mount_point="sudo mkdir -v " + luks_drive_mount_point
  mount_luks_cmd = "sudo mount /dev/mapper/" + luks_device_name + " " + luks_drive_mount_point

  print("Enter sudo password if necessary:")
  os.system(open_luks_cmd)
  os.system(create_luks_mount_point)
  os.system(mount_luks_cmd)

def unmountLuks(config):
  luks_drive_mount_point=config['settings']['luks_drive_mount_point']
  luks_device_name=config['settings']['luks_device_name']
  remove_luks_mount_point="sudo rmdir -v " + luks_drive_mount_point

  print("Enter sudo password if necessary:")
  os.system("sudo umount " + luks_drive_mount_point )
  os.system(remove_luks_mount_point)
  os.system("sudo cryptsetup luksClose /dev/mapper/" + luks_device_name )

def main():
  parser = argparse.ArgumentParser(description='Automate backup process. Run without arguments \
                                   to open LUKS, backup stuff, and close LUKS.')
  parser.add_argument("-m", "--mount",
                      action="store_true", dest="mountLuks", default=False,
                      help="Only mount LUKS drive, and exit")
  parser.add_argument("-u", "--unmount",
                      action="store_true", dest="unmountLuks", default=False,
                      help="Only UNmount LUKS drive, and exit")
  parser.add_argument("-b", "--backup",
                      action="store_true", dest="do_backup", default=False,
                      help="Only do backup, don't mount or unmount anything")
  parser.add_argument("-r", "--remote-backup",
                      action="store_true", dest="do_remote_backup", default=False,
                      help="Only do remote backup, (ignores rsync list)")
  parser.add_argument("-d", "--decrypt-remote-backup",
                      dest="remote_backup_archive_name", default="",
                      help="Decrypt remote backup archive (*.tar.gz.gpg)")

  args = parser.parse_args()
  global config
  config = parse_config_file()

  if args.mountLuks:
    mountLuks(config)
  elif args.unmountLuks:
    unmountLuks(config)
  elif args.do_backup:
    backup(config)
  elif args.do_remote_backup:
    remote_backup()
  elif args.remote_backup_archive_name:
    decrypt_remote_backup(args.remote_backup_archive_name)
  else:
    mountLuks(config)
    backup(config)
    unmountLuks(config)

if __name__ == "__main__":
  main()
