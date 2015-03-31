#!/usr/bin/env python
 
# pybackup - ease regular encrypted backups
# Copyright (C) 2014 Óscar Pereira

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
import signal
import subprocess as sp
import json
from time import time
from datetime import date
from getpass import getpass, GetPassWarning
import argparse
from shlex import quote
import subprocess
from shutil import which
from ntpath import basename

config = None

def check_deps():
  if which("cryptsetup") is None:
    print("cryptsetup not found!")
    return False
  if which("gpg") is None:
    print("gnupg (gpg binary) not found!")
    return False
  if which("pv") is None:
    print("pv not found!")
    return False
  if which("scp") is None:
    print("scp not found!")
    return False
  if which("rsync") is None:
    print("rsync not found!")
    return False
  if which("tar") is None:
    print("tar not found!")
    return False
  if which("gzip") is None:
    print("gzip not found!")
    return False

  return True

##
# @brief Centralised place where to obtain the names of the files to be created.
#
# @param name A key identifying the file to be created (e.g. TAR archive).
#
# @return The requested name.
#
def get_name(name):
  computer=config['settings']['computer']
  user=config['settings']['user']
  backup_date=date.today().strftime("%Y%b%d")

  # path for dir where tmp files are to be created
  backup_dir=config['settings']['backup_tmp_path'] 

  if name == "tar_archive_name":
    return backup_dir + "/bck-" + computer + "-" + backup_date + ".tar.gz"
  elif name == "encrypted_tar_archive_name":
    return backup_dir + "/bck-" + computer + "-" + backup_date + ".tar.gz.gpg"

##
# @brief Create TAR archive which will be backed up.
#
# @return the full path of the created TAR archive.
#
def create_tar_archive():
  directories=' '.join([ quote(i) for i in config['dirs']['directories'] ])
  root_directories=' '.join([ quote(i) for i in config['dirs']['root_directories'] ])
  excluded_directories=' '.join([ quote(i) for i in config['dirs']['directories_excl'] ])
  excluded_directories_cmd=' --exclude='.join([ quote(i) for i in config['dirs']['directories_excl'] ])
  excluded_directories_cmd=' --exclude=' + excluded_directories_cmd
  user=config['settings']['user'] # for chown'ing the tar file to the user (instead of root)

  tar_archive_name = get_name("tar_archive_name")
  if os.path.exists(tar_archive_name):
    print("Archive " + tar_archive_name + " exists; skipping archive creation...\n")
    return ""

  print("Creating TAR archive... ", end="", flush=True)
  dirs_size = sp.check_output("du -sbc " + directories + " " + root_directories 
                              + " | tail -1 | awk '{print $1}'", shell=True)
  aux = sp.check_output("du -sbc " + excluded_directories 
                        + " | tail -1 | awk '{print $1}'", shell=True)
  dirs_size = str(int(dirs_size) - int(aux))
  sp.call("tar -cf - " + directories + " " + root_directories + " " 
          + excluded_directories_cmd + " | pv --wait -s " + dirs_size 
          + " | gzip > " + tar_archive_name, shell = True, stdout = sp.PIPE )
  sp.call("chown " + user + " " + tar_archive_name, shell=True)
  print("Done creating TAR file!")

  return tar_archive_name

def delete_tar_archive(tar_archive_path):
  '''Delete tar archive in tar_archive_path'''
  user=config['settings']['user']
  print("Removing TAR archive... ", end="", flush=True)
  sp.call("sudo -u " + user + " rm -rf " + tar_archive_path, shell = True)
  print("DONE!")

def backup(tar_archive_path):
  '''Does the backup of tar ONLY. Assumes all drives are mounted 
  (and leaves them like that)'''
  # extract needed info from config file
  computer=config['settings']['computer']
  user=config['settings']['user']
  luks_drive_mount_point=config['settings']['luks_drive_mount_point']
  backup_dir_name=config['settings']['backup_dir_name']
  backup_dir=luks_drive_mount_point + "/" + backup_dir_name
  backup_archive_name = basename(tar_archive_path)

  print("Copying TAR file...", end="", flush=True)
  sp.call("sudo -u " + user + " pv " + tar_archive_path + " > " 
          + backup_dir+ "/" + backup_archive_name , shell=True)

##
# @brief Does remote backup. It encrypts a TAR archive and copies it a remote
# location.
#
# The encrypted archive is *always* deleted before the function returning.
#
# up @param tar_archive_path - the tarball's path
#
# @return void
#
def remote_backup(tar_archive_path, passphrase):
  # --- BEGIN get data from config file --- #
  user = config["settings"]["user"]

  # where to place the encryted archive in the remote server
  remote_backup_dir_name=config['settings']['remote_backup_dir_name']

  # remote server
  remote_site=config['settings']['remote_site']
  # --- END get data from config file --- #

  backup_dir=get_name("encrypted_tar_archive_name")
  if (not os.path.exists(os.path.dirname(backup_dir))):
    print ("Backup tmp path does NOT exist: ", backup_dir, "\nExiting...")
    return

  # encrypt and scp the result
  try:
    print ("Creating encrypted backup archive...")
    enc_archive_name = get_name("encrypted_tar_archive_name")
    sp.call("sudo -u " + user + " pv " + tar_archive_path + 
            " | gpg --symmetric --batch --passphrase \"" + passphrase 
            + "\" --no-tty --cipher-algo aes256 --force-mdc -o " 
            + enc_archive_name , shell=True)

    print ("Transfering encrypted backup archive to remote location...")
    sp.call("sudo -u " + user + " scp " + enc_archive_name + " " + remote_site 
            + ":" + remote_backup_dir_name, shell=True)

    # delete encrypted archive
    sp.call("sudo -u " + user + " rm -rf " + enc_archive_name, shell = True) 
    print("DONE!")
  except GetPassWarning:
    print("Could not read passphrase. Exiting...")

def decrypt_remote_backup(encrypted_file, path_for_decrypted=""): 
  '''Aborts if encrypted file does NOT have a name like: filename.tar.gz.gpg'''
  
  if not encrypted_file.endswith(''):
    print("Encrypted file must have a name like: filename.tar.gz.gpg")
    return False

  if path_for_decrypted != "": 
    path_for_decrypted = os.path.expanduser(path_for_decrypted)

  if path_for_decrypted != "" and not os.path.isdir(path_for_decrypted):
    print("Path for decrypted archive must be directory! Exiting...\n")
    return False

  if not path_for_decrypted.endswith("/"):
    path_for_decrypted = path_for_decrypted + "/"

  try:
    passphrase = getpass(prompt='Please enter decryption passphrase: ')

    print ("Decrypting backup archive... (this can take a few minutes)")
    sp.call("echo -n \"" + quote(passphrase) + 
        "\" | gpg --passphrase-fd 0 --no-tty --cipher-algo aes256 --force-mdc " +
        "--decrypt --batch " + encrypted_file + " > " + 
        quote(path_for_decrypted) + quote(encrypted_file[:-4]), shell=True, stdout=sp.PIPE)
    del passphrase
  except GetPassWarning:
    print("Could not read passphrase. Exiting...")

def do_rsync_backup():
  luks_drive_mount_point=config['settings']['luks_drive_mount_point']
  backup_dir_name=config['settings']['backup_dir_name']
  backup_dir=luks_drive_mount_point + "/" + backup_dir_name + "/rsync/"

  rsync_directories=[ quote(i) for i in config['dirs']['rsync_directories'] ]
  print("Starting rsync...", end="", flush=True)
  for folder in rsync_directories:
    # strip trailing slash in folder, if there is one
    # otherwise rsync copies the *contents* of the folder instead of the folder itself
    # WHICH IS PROBLEMATIC BECAUSE OF DELETE
    if folder.endswith('/'): folder = folder[:-1]
    try:
      output = sp.check_output("rsync -avz --human-readable --progress --delete-during --exclude=\"*.swp\" "
          + folder + " " + backup_dir, shell=True,)
      print(output) # TODO get rid of this bytearray...
    except Exception as e:
      print("Rsync for %s **FAILED**: %s" % (folder, str(e)))

def parse_config_file():
  script_path=os.path.dirname(__file__)
  if len(script_path) > 0:
    script_path=script_path+"/"
  try:
    json_data=open(script_path + 'backup.json')
    data=json.load(json_data)
    return data
  except Exception as e:
    print("Could not parse config file: %s" % str(e))
    exit(-1)
  # raise
  # useful for debug
  #from pprint import pprint
  #pprint(data)

def mountLuks():
  luksUUID=config['settings']['luksUUID']
  luks_device_name=config['settings']['luks_device_name']
  luks_drive_mount_point=config['settings']['luks_drive_mount_point']

  # check if luks_drive_mount_point does NOT exist: error otherwise
  if (os.path.exists(luks_drive_mount_point)):
    raise RuntimeError("LUKS mount point (" + luks_drive_mount_point + ") exists!\nExiting...")

  open_luks_cmd = "cryptsetup open --type luks UUID=" + luksUUID + " " + luks_device_name + " 2>&1 > /dev/null"
  create_luks_mount_point="mkdir -v " + luks_drive_mount_point
  mount_luks_cmd = "mount /dev/mapper/" + luks_device_name + " " + luks_drive_mount_point
  remove_luks_mount_point="rmdir -v " + luks_drive_mount_point

  ret_code = None
  print("Enter password if necessary!")
  try: # TODO handle this properly! (error capture)
    ret_code = sp.call(open_luks_cmd, shell=True)
    if ret_code != 0:
      print("Unable to mount LUKS drive: is it connected?")
      return # exit try block
    sp.call(create_luks_mount_point, shell=True)
    sp.call(mount_luks_cmd, shell=True)
  except:
    print("Ups!")
    sp.call(remove_luks_mount_point)

  if ret_code != 0:
    return False
  return True

def unmountLuks():
  luks_drive_mount_point=config['settings']['luks_drive_mount_point']
  luks_device_name=config['settings']['luks_device_name']
  remove_luks_mount_point="rmdir -v " + luks_drive_mount_point

  # check that the LUKS mount point really has a LUKS drive mounted
  devnull=open("/dev/null", "w")
  p1=subprocess.Popen(["mount" ], stdout=subprocess.PIPE)
  p2=subprocess.Popen(["grep", luks_drive_mount_point], stdin=p1.stdout, stdout=devnull, stderr=devnull)
  p1.stdout.close()
  p2.communicate()[0]
  if(p2.returncode != 0): # TODO run another grep for /dev/mapper
    print ("LUKS mount point is ", luks_drive_mount_point, "\nBut LUKS drive not mounted there! Exiting...")
    return

  print("Enter password if necessary:")
  sp.call("umount " + luks_drive_mount_point, shell=True)
  sp.call(remove_luks_mount_point, shell=True)
  sp.call("cryptsetup close " + luks_device_name, shell=True)

def get_passphrase():
  try:
    passphrase = "1"
    passphrase1 = "2"
    while passphrase != passphrase1:
      passphrase = getpass(prompt='Please enter encryption passphrase: ')
      passphrase1 = getpass(prompt='Please enter encryption passphrase again: ')
      if passphrase != passphrase1:
        print("Passphrases did NOT match! Try again...")
    del passphrase1
    return passphrase
  except GetPassWarning:
    # print("Could not read passphrase. Exiting...")
    raise

def main():
  if not check_deps():
    exit(-1)

  global config
  config = parse_config_file()

  parser = argparse.ArgumentParser(description='Automate backup process. **MUST \
                                                BE RAN WITH _sudo_**! Run without arguments \
                                                to open LUKS, backup stuff (tar, \
                                                rsync AND remote), and close LUKS.')
  parser.add_argument("-m", "--mount",
                      action="store_true", dest="mountLuks", default=False,
                      help="Only mount LUKS drive, and exit")
  parser.add_argument("-u", "--unmount",
                      action="store_true", dest="unmountLuks", default=False,
                      help="Only UNmount LUKS drive, and exit")
  parser.add_argument("-b", "--backup",
                      action="store_true", dest="do_backup", default=False,
                      help="Mount LUKS drive, do LOCAL backup (i.e. tar and \
                      rsync but NOT remote), unmount.")
  parser.add_argument("-r", "--remote-backup",
                      action="store_true", dest="do_remote_backup", default=False,
                      help="Only do remote backup, (ignores local tar and rsync list)")
  parser.add_argument("-R", "--rsync-backup",
                      action="store_true", dest="do_rsync_backup", default=False,
                      help="Only do rsync backup, (ignores tar and remote list)")
  parser.add_argument("-d", "--decrypt-remote-backup",
                      dest="opt_decrypt_remote_backup", nargs='+',
                      metavar=("encryptedbackup.tar.gz.gpg", "output_dir"),
                      help="Decrypt remote backup archive (*.tar.gz.gpg)")
  # TODO the nargs='+' is the last argument is not ideal; see
  # https://stackoverflow.com/questions/23172172/range-for-nargs-in-argparse
  # TODO it seems that dest cannot be the name of a function, otherwise it
  # always gets called...

  # if -h given, control exits after the next line
  args = parser.parse_args()

  # check we're running with sudo
  if os.getuid() != 0 and not args.opt_decrypt_remote_backup:
    print("Please run with sudo!")
    exit(-1)

  if args.mountLuks:
    mountLuks()
  elif args.unmountLuks:
    unmountLuks()
  elif args.do_backup:
    if not mountLuks():
      return
    tar_archive_path = create_tar_archive()
    if tar_archive_path == "":
      unmountLuks()
      return

    backup(tar_archive_path)
    delete_tar_archive(tar_archive_path)

    do_rsync_backup()
    unmountLuks()
  elif args.do_remote_backup:
    tar_archive_path = create_tar_archive()
    passphrase = get_passphrase()
    remote_backup(tar_archive_path, passphrase)
    del passphrase
    delete_tar_archive(tar_archive_path)
  elif args.do_rsync_backup:
    if not mountLuks():
      return
    do_rsync_backup()
    unmountLuks()
  elif args.opt_decrypt_remote_backup:
    if len(args.opt_decrypt_remote_backup) == 1:
      decrypt_remote_backup(args.opt_decrypt_remote_backup[0])
    elif len(args.opt_decrypt_remote_backup) == 2:
      decrypt_remote_backup(args.opt_decrypt_remote_backup[0], 
                            args.opt_decrypt_remote_backup[1])
    else:
      print("Decrypting backup takes one mandatory argument\n"
          "(the encrypted archive file path), and one optional one\n"
          "(the path where to save the decrypted archive)\n")
      exit(-1)
  else:
    if not mountLuks():
      return

    tar_archive_path = create_tar_archive()
    if tar_archive_path == "":
      unmountLuks()
      return
    backup(tar_archive_path)
    passphrase = get_passphrase()
    remote_backup(tar_archive_path, passphrase)
    del passphrase
    delete_tar_archive(tar_archive_path)

    do_rsync_backup()
    unmountLuks()

def exit_gracefully(signum, frame):
  # restore the original signal handler as otherwise evil things will happen
  # in raw_input when CTRL+C is pressed, and our signal handler is not re-entrant
  signal.signal(signal.SIGINT, original_sigint)

  user=config['settings']['user']
  tmp_path=config['settings']['backup_tmp_path']
  sp.call("sudo -u " + user + " rm -rf " + tmp_path + "/*", shell = True)
  unmountLuks()

  exit()

if __name__ == "__main__":
  original_sigint = signal.getsignal(signal.SIGINT)
  signal.signal(signal.SIGINT, exit_gracefully)
  main()
