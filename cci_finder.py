#!/usr/bin/env python

######
# Copyright 2016 Google Inc.
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
# http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# 
########
# Pexpect script, used to get output and write it to a file.
# Reads the output of 'show ap arm state' and
# pull out the ap-name, cci neighbors & their SNR
# Also writes the output to cci-aps.csv
# usage:
# run it with '-h' for optional arguments.
# you can optionally have a gpg encrypted file in your home directoray named ".switchpass.gpg" 
# that contains only 2 lines (user & password), to be used for credentials. Otherwise follow prompts
# Mike Albano. Updated 2016-01-27
########

import os, os.path, pexpect, sys, re, getpass, argparse

# Clear existing file, and make sure we can write to a new one
# note, /tmp/wmc_output will remain on system, so subsequent runs can be done
# without needing to re-login to wlc. Example, changing SNR (-s) value to see new results.
try:
  check = open('cci-aps.csv', 'w')
  check2 = open('/tmp/test', 'w')
  check.close()
# if not, print error message and exit
except:
  print "can't write to files (~cci-aps.csv & /tmp/test). Ensure directory permissions allow this"
  sys.exit(1)

## Argument Parser
parser = argparse.ArgumentParser(description='Identify CCI neighbors of Campus APs')
# Add examples, after the --help option
parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,epilog='\nIf logging in to wlc (not useing \'-f\' option) this program requires \'pexpect\'. Eg easy_install pexpect.\n\nExample > python cci_finder.py -wlc controller1.test.net\nExample \(2.4GHz neighbors\)> python graph-output.py -2.4 -wlc controller1.test.net \nExample \(5GHz neighbors, specifying filename\)> python graph-output.py -f cli_output.txt\nExample \(5GHz neighbors, specifying SNR of 20\) > python cci_finder.py -wlc controller1.nets.net -s 20 \nDefault \(if no option specified\) is 5Ghz neighbors only and prompting user for controller FQDN & credentials\n\n')
# nargs = # of default allowed options to a switch, const = default value
# nargs='?' makes the const value get auto-supplied, IF the option is given without a value
parser.add_argument('-r', '--radio', type=str, help='Choose frequency of interest. 2.4, 5, or both. (Default=\'5\' only)', choices=['2.4', '5', 'both'], default='5', required=False)
parser.add_argument('-s', '--snr', nargs='?', const='14', type=int, help='Choose minimum SNR for inclusion in report. (Default=\'14dB\')', default=14, required=False)
# Require one of the following arguments (either a filename or wlc)
group_arg = parser.add_mutually_exclusive_group(required=True)
group_arg.add_argument('-f', '--filename', type=str, help='specify filename of \'show ap arm state\' output, instead of logging in.')
group_arg.add_argument('-wlc', '--controller', type=str, help='specify FQDN or IP of the wireless controller.')
args = vars(parser.parse_args())
# Assign variables to the arguments provided
wlc = args['controller']
snr = args['snr']
radio = args['radio']
filename = args['filename']
# Additional help (printed with -h/--help)

# check if gpg encrypted file exists for credentials
home_dir_expand = os.path.expanduser("~")
creds_filename = ".switchpass.gpg"
if os.path.isfile(os.path.join(home_dir_expand, creds_filename)):
  #open the gpg file, and define some variables to be used later for credentials.
  passwd = os.popen('gpg -d --quiet --batch ~/.switchpass.gpg')
  passwd_decrypted = passwd.readlines()
  username_only = passwd_decrypted[0].strip('\n')
  passwd_only = passwd_decrypted[1].strip('\n')
  passwd.close()
# if no gpg file, prompt user for creds
else:
  # Get credentials, only if no '-f' option specified
  if not filename:
    username_only = raw_input("Enter username (or hit enter to use \"%s\"): " % getpass.getuser())
    if not username_only:
      username_only = getpass.getuser()
    passwd_only = getpass.getpass()

output_file = open('cci-aps.csv', 'w')
# Write the CSV header
output_file.write("Access Point,Channel,CCI Neighbor AP,SNR of Neighbor\n")

def ssh_to(wlc):
  # temporary working file for show command outputs
  out_file1 = open('/tmp/wmc_output', 'w')
  child = pexpect.spawn('/usr/bin/ssh -o StrictHostKeyChecking=no %s@%s' % (username_only, wlc))
  child.logfile = None
  initial = child.expect([pexpect.TIMEOUT, 'Connection refused', 'Connection reset by peer', 'No route to host', 'Connection closed by remote host', 'not known\r\r\n', 'assword: '], timeout=10)
  if initial == 0:
    print "Waiting for SSH to return a prompt...(taking long)..."
    child.kill(0)
  elif initial == 1:
    print "Connection Refused from host"
  elif initial == 2:
    print "Connection reset by peer"
  elif initial == 3:
    print "No route to host"
  elif initial == 4:
    print "Connection closed by remote host"
  elif initial == 5:
    print "Could not resolve hostname: %s" % wlc
    child.kill(0)
  elif initial == 6:
    child.sendline(passwd_only)
  # After sending passowrd, expect/do the following
  offer = child.expect(['interactive\).', '#', pexpect.TIMEOUT], timeout=10)
  if offer == 0:
    print "Permission Denied (failed login) for %s" % wlc
    child.kill(0)
  elif offer == 1:
    print "logged in succesfully, running command(s) on: %s" % wlc
    child.sendline('no paging')
    child.expect('#')
    out_file1.write(child.before)
    out_file1.write('\n')
    if radio == '2.4':
      child.sendline('show ap arm state dot11g')
    if radio == 'both':
      child.sendline('show ap arm state')
    else:
      child.sendline('show ap arm state dot11a')
    child.expect('#')
    out_file1.write(child.before)
    child.sendline("exit")
    print "Done..."
    child.close()
    out_file1.close()
    find_cci('/tmp/wmc_output')
  elif offer == 2:
    print "ssh connection timed out on %s" % wlc
    child.kill(0)

def find_cci(file):
  # If filename given, analyze that instead of logging in to controller
  # else, analyze the file handed from pexpect function
  if filename:
    input_file = open(filename).readlines()
  else:
    input_file = open(file).readlines()
  for line in input_file:
    # Find AP Name & its channel
    ap_channel_search = re.search(r'(AP\:)([^\s]+)(.*Channel\:)([^\s]+)', line, re.IGNORECASE)
    # Find cci aps and their channel & SNR
    snr_channel_search = re.search(r'(.*\b)(\s+)(\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b)(\s+)([0-9]+)(\s+[0-9]+)(\s+)([0-9]+)', line, re.IGNORECASE)
    if ap_channel_search:
      # define the current AP
      current_ap = ap_channel_search.group(2)
      # define the APs current channel
      current_channel = ap_channel_search.group(4)
    if snr_channel_search:
      snr_ap = snr_channel_search.group(1)
      snr_ap_snr = snr_channel_search.group(5)
      snr_ap_channel = snr_channel_search.group(8)
      # Make sure the minimum SNR is reached, print the matches & write them to CSV
      if current_channel == snr_ap_channel and int(snr_ap_snr) > (snr - 1):
        print "AP: %s on channel %s has co-channel neighbor: %s with SNR: %s" % (current_ap,current_channel,snr_ap,snr_ap_snr)
        output_file.write(current_ap)
        output_file.write(',')
        output_file.write(current_channel)
        output_file.write(',')
        output_file.write(snr_ap)
        output_file.write(',')
        output_file.write(snr_ap_snr)
        output_file.write('\n')
  output_file.close()

# If filename given, analyze that instead of logging in to controller
if filename:
  find_cci(filename)
else:
  ssh_to(wlc)

print "CSV written -- \'cci-aps.csv\'"

sys.exit(0)
