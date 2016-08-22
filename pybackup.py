#!/usr/bin/env python
 
# pybackup - ease regular encrypted backups
# Copyright (C) 2016 Óscar Pereira

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

import signal
import subprocess as sp
import json
import argparse
from platform import node
from datetime import date
from getpass import getuser
from os.path import exists, dirname, expanduser
from ntpath import basename

from shlex import quote
from shutil import which
from time import time

_luks_device_name       = "luksBackupDevice"
_luks_drive_mount_point = "mntLUKS"

# these are filled (or changed) by main()
# _tmp_path is also expanded when value from config is read in
config           = None
_user            = ""
_computer        = ""
_tmp_path        = expanduser("~") 
_backup_dir_name = "."

def check_deps():
  if which("cryptsetup") is None:
    print("cryptsetup not found!")
    return False
  if which("pv") is None:
    print("pv not found!")
    return False
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

# constructs and returns the full path (and name) of the tarball...
def get_name():
  backup_date=date.today().strftime("%Y%b%d")
  epoch=str(int(time()))

  return _tmp_path + "/bck-" + epoch + "-" + _computer + "-" + backup_date + ".tar.gz"

##
# @brief Create TAR archive which will be backed up.
#
# @return the full path of the created TAR archive.
#
def create_tar_archive():
  directories=[ quote(expanduser(i)) for i in config['dirs']['directories'] ]
  root_directories=[ quote(expanduser(i)) for i in config['dirs']['root_directories'] ]
  excluded_directories_for_du=[ quote(expanduser(i)) for i in config['dirs']['directories_excl'] ]
  excluded_directories_for_tar=[ '--exclude=' + quote(expanduser(i)) 
                                 for i in config['dirs']['directories_excl'] ]

  tar_archive_name = get_name()
  if exists(tar_archive_name):
    print("Archive " + tar_archive_name + " exists; skipping archive creation...\n")
    return ""

  # get size of dirs to backup
  p1 = sp.Popen(["sudo", "du", "-sbc"] + directories + root_directories,
                stdout=sp.PIPE)
  p2 = sp.Popen(["tail", "-1"], stdin=p1.stdout, stdout=sp.PIPE)
  p3 = sp.Popen(["cut", "-f1"], stdin=p2.stdout, stdout=sp.PIPE, stderr=sp.DEVNULL)
  # p1.stdout.close()
  # p2.stdout.close()
  dirs_size = p3.stdout.read()

  # get size of dirs to exclude (needed for progress bar to be accurate)
  p1 = sp.Popen(["sudo", "du", "-sbc"] + excluded_directories_for_du, stdout=sp.PIPE)
  p2 = sp.Popen(["tail", "-1"], stdin=p1.stdout, stdout=sp.PIPE)
  p3 = sp.Popen(["cut", "-f1"], stdin=p2.stdout, stdout=sp.PIPE, stderr=sp.DEVNULL)
  size_of_excluded = p3.stdout.read()

  dirs_size = str(int(dirs_size) - int(size_of_excluded))

  # now create the tarball...
  print("Creating TAR archive... ", end="", flush=True)
  # next line adds basedir to tarball ([:-7] strips the .tar.gz from tar_archive_name)
  transform_regex = "s,^," + basename(tar_archive_name)[:-7] + "/," 
  p1 = sp.Popen(["sudo", "tar", "cf", "-", "--transform", transform_regex] + 
                excluded_directories_for_tar + directories + 
                root_directories , stdout=sp.PIPE)
  p2 = sp.Popen(["pv", "--wait", "-s", dirs_size ], stdin=p1.stdout, stdout=sp.PIPE)
  with open(tar_archive_name, 'wb') as t:
    p3 = sp.Popen(["gzip"], stdin=p2.stdout, stdout=t, stderr=sp.DEVNULL)
    errno = p3.communicate()[1]
    print(errno)

  # make sure user owns his data
  sp.call(["chown", _user, tar_archive_name], shell=False)
  print("Done creating TAR file!")

  return tar_archive_name

def delete_tar_archive(tar_archive_path):
  '''Delete tar archive in tar_archive_path'''

  print("Removing TAR archive... ", end="", flush=True)
  sp.call(["rm", "-rf", tar_archive_path], shell=False)
  print("DONE!")

def backup(tar_archive_path):
  '''Does the backup (i.e. copy) of tar ONLY. Assumes all drives are mounted 
  (and leaves them like that)'''

  if not ("directories" in config['dirs'] or 
          "root_directories" in config['dirs']):
    return True # we quit, but for legitimate reasons (nothing to do)

  full_luks_mount_point = _tmp_path + "/" + _luks_drive_mount_point
  backup_dir=full_luks_mount_point + "/" + _backup_dir_name
  backup_archive_name = basename(tar_archive_path)

  # check _backup_dir_name exists; offer to create it otherwise
  if not (exists(backup_dir)):
    question = "Destination dir (" + _backup_dir_name + \
        ") does not exist in destination device. Create?"
    reply = ''
    while reply != 'y' and reply != 'n':
      reply = str(input(question+' (y/n): ')).lower().strip()

    if reply == 'n':
      return False

    # otherwise create directory
    try:
      create_backup_dir_cmd="mkdir -v -p " + backup_dir
      sp.call(create_backup_dir_cmd.split(' '), shell=False)
    except:
      print("Could not create dir in destination device!")
      return False

  print("Copying TAR file...", end="", flush=True)
  with open(backup_dir + "/" + backup_archive_name, 'wb') as t:
    p = sp.Popen(["sudo", "-u", _user, "pv", tar_archive_path], stdout=t)
    p.wait()
    if p.returncode != 0:
      print("Copying tarball FAILED, with code %d" % p.returncode)
      return False
    return True

def do_rsync_backup():
  if not "rsync_directories" in config['dirs']:
    return True # we quit, but for legitimate reasons (nothing to do)

  backup_dir= _tmp_path + "/" + _luks_drive_mount_point + "/" + _backup_dir_name + "/rsync/"

  # check _backup_dir exists; offer to create it otherwise
  if not (exists(backup_dir)):
    question = "Destination dir for rsync (" + backup_dir + \
        ") does not exist in destination device. Create?"
    reply = ''
    while reply != 'y' and reply != 'n':
      reply = str(input(question+' (y/n): ')).lower().strip()

    if reply == 'n':
      return False

    # otherwise create directory
    try:
      create_backup_dir_cmd="mkdir -v -p " + backup_dir
      sp.call(create_backup_dir_cmd.split(' '), shell=False)
    except:
      print("Could not create rsync dir in destination device!")
      return False

  rsync_directories=[ quote(expanduser(i)) for i in config['dirs']['rsync_directories'] ]
  print("Starting rsync...", end="", flush=True)
  for folder in rsync_directories:
    # strip trailing slash in folder, if there is one
    # otherwise rsync copies the *contents* of the folder instead of the folder itself
    # WHICH IS PROBLEMATIC BECAUSE OF DELETE
    if folder.endswith('/'): folder = folder[:-1]

    try:
      p = sp.Popen(["rsync", "-avz", "--human-readable", "--progress",
                    "--delete-during", "--exclude=\"*.swp\"", folder,
                    backup_dir], stdout=sp.PIPE)
      while p.poll() is None:
        l = p.stdout.readline() # This blocks until it receives a newline.
        print(l.decode('utf-8'), end="")
    except Exception as e:
      print("Rsync for %s **FAILED**: %s" % (folder, str(e)))

def parse_config_file():
  script_path=dirname(__file__)
  if len(script_path) > 0:
    script_path=script_path+"/"
  try:
    json_data=open(script_path + 'backup.json')
    data=json.load(json_data)
  except Exception as e:
    print("Could not parse config file: %s" % str(e))
    exit(-1)
  # raise

  # get rid of empty "values"
  data = _clean_dict(data)

  if _check_config(data):
    return data
  return False

  # useful for debug
  # from pprint import pprint
  # pprint(data)
  # exit(-1)

# keys are either for dics, lists, or strings
def _clean_dict(d):
  for k in list(d): # this copies the key list; needed because of del
    if isinstance(d[k], dict):
      d[k] = _clean_dict(d[k])
      if d[k] == {}: del d[k]
    elif isinstance(d[k], list):
      d[k] = _clean_list(d[k])
      if d[k] == []: del d[k]
    elif isinstance(d[k], str):
      if d[k] == '': del d[k]
  return d

# the lists in the config are all of strings, so code here is simple
def _clean_list(l):
  return [ i for i in l if i != '' ]

def _check_config(d):
  if not "luksUUID" in d['settings']:
    print("Where am I suppose to back up to?")
    return False
  if not ("directories" in d['dirs'] or "rsync_directories" in d['dirs']):
    print("What am I suppose to back up?")
    return False
  return True

# NOTE: this creates _tmp_path if it does not exist.
def mountLuks():
  luksUUID=config['settings']['luksUUID']
  full_luks_mount_point = _tmp_path + "/" + _luks_drive_mount_point

  # check if full_luks_mount_point does NOT exist: error otherwise
  if (exists(full_luks_mount_point)):
    raise RuntimeError("LUKS mount point (" + full_luks_mount_point + ") exists!\nExiting...")

  open_luks_cmd = "sudo cryptsetup open --type luks UUID=" + luksUUID \
                  + " " + _luks_device_name + " 2>&1 > /dev/null"
  # open_luks_cmd = "sudo cryptsetup open --type luks " + "/mnt/wd500/foo.img" \
                  # " " + _luks_device_name + " 2>&1 > /dev/null"
  create_luks_mount_point="mkdir -v -p " + full_luks_mount_point
  mount_luks_cmd = "sudo mount /dev/mapper/" + _luks_device_name + "" \
                   " " + full_luks_mount_point
  remove_luks_mount_point="rmdir -v " + full_luks_mount_point

  ret_code = None
  try: # TODO handle this properly! (error capture)
    ret_code = sp.call(open_luks_cmd.split(' '), shell=False)
    if ret_code != 0:
      print("Unable to mount LUKS drive: is it connected?")
      return # exit try block
    sp.call(create_luks_mount_point.split(' '), shell=False)
    sp.call(mount_luks_cmd.split(' '), shell=False)
  except:
    print("Ups!")
    sp.call(remove_luks_mount_point)

  if ret_code != 0:
    return False
  return True

def unmountLuks():
  full_luks_mount_point = _tmp_path + "/" + _luks_drive_mount_point
  remove_luks_mount_point="rmdir -v " + full_luks_mount_point

  # check that the LUKS mount point really has a LUKS drive mounted
  p1=sp.Popen(["sudo", "mount" ], stdout=sp.PIPE)
  p2=sp.Popen(["grep", _luks_drive_mount_point], stdin=p1.stdout,
              stdout=sp.DEVNULL, stderr=sp.DEVNULL)
  p1.stdout.close()
  p2.communicate()[0]
  if(p2.returncode != 0): # TODO run another grep for /dev/mapper
    print ("LUKS mount point is ", full_luks_mount_point,
           "\nBut LUKS drive not mounted there! Exiting...")
    return

  sp.call([ "sudo", "umount", full_luks_mount_point ], shell=False)
  sp.call(remove_luks_mount_point.split(' '), shell=False)
  sp.call([ "sudo", "cryptsetup", "close", _luks_device_name ], shell=False)

def main():
  if not check_deps():
    exit(-1)

  #
  # parse config and fill globals with it
  #
  global config
  config = parse_config_file()
  if not config:
    exit(-1)
  global _computer
  if 'computer' in config['settings']:
    _computer = config['settings']['computer']
  else:
    _computer = node()
  global _user
  if 'user' in config['settings']:
    _user = config['settings']['user']
  else:
    _user = getuser()
  global _tmp_path
  if 'tmp_path' in config['settings']:
    _tmp_path = expanduser(config['settings']['tmp_path'])
  global _backup_dir_name
  if 'backup_dir_name' in config['settings']:
    _backup_dir_name = config['settings']['backup_dir_name']

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
  parser.add_argument("-R", "--rsync-backup",
                      action="store_true", dest="do_rsync_backup", default=False,
                      help="Only do rsync backup, (ignores tar and remote list)")
  # TODO it seems that dest cannot be the name of a function, otherwise it
  # always gets called...

  # if -h given, control exits after the next line
  args = parser.parse_args()

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

    if not backup(tar_archive_path):
      print("Could not copy tarball to backup device; perhaps dest folder is missing?")
      delete_tar_archive(tar_archive_path)
    else:
      delete_tar_archive(tar_archive_path)
      do_rsync_backup()

    unmountLuks()
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
    print("Please choose option!")

def exit_gracefully(signum, frame):
  # restore the original signal handler as otherwise evil things will happen
  # in raw_input when CTRL+C is pressed, and our signal handler is not re-entrant
  signal.signal(signal.SIGINT, original_sigint)

  # XXX because _tmp_path can now be ~, check carefully what to do with next
  # line...
  # sp.call("sudo -u " + _user + " rm -rf " + _tmp_path + "/*", shell = True)
  unmountLuks()

  exit()

if __name__ == "__main__":
  original_sigint = signal.getsignal(signal.SIGINT)
  signal.signal(signal.SIGINT, exit_gracefully)
  main()

# TODO add option of calling functions with verbose output or not...
