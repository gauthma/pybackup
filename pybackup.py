#!/usr/bin/env python

# pybackup - ease regular encrypted backups
# Copyright (C) 2012 Oscar Pereira

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import json
from time import time
from datetime import date
import argparse

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

  # now handle backup (TODO: handle the sudo request, if user runs only backup, and sudo
  # credentials have expired)
  os.system("tar -cf - " + directories + " | pv -s $(du -sbc " + directories +
            " | tail -1 | awk '{print $1}') | gzip > " + backup_dir + "/" + tar_archive_name )
  os.system("sudo tar -cf - " + root_directories + " | pv -s $(du -sbc " + root_directories +
            " |  tail -1 | awk '{print $1}') | gzip > " + backup_dir + "/" + root_tar_archive_name)

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
    # useful for debug
    #from pprint import pprint
    #pprint(data)
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

  args = parser.parse_args()
  config = parse_config_file()

  if args.mountLuks:
    mountLuks(config)
  elif args.unmountLuks:
    unmountLuks(config)
  elif args.do_backup:
    backup(config)
  else:
    mountLuks(config)
    backup(config)
    unmountLuks(config)

if __name__ == "__main__":
  main()
