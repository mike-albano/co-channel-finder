# co-channel-finder
Identify CCI neighbors of Campus APs

Usage: python cci_finder.py -h

Pexpect script, used to get output and write it to a file.
Reads the output of 'show ap arm state' and pull out the ap-name, cci neighbors & their SNR.

Also writes the output to cci-aps.csv.

You can optionally have a gpg encrypted file in your home directoray named ".switchpass.gpg" that contains only 2 lines (user & password), to be used for credentials. Otherwise follow prompts.

Examples

Example > python cci_finder.py -wlc controller1.test.net
Example (2.4GHz neighbors)> python graph-output.py -2.4 -wlc controller1.test.net
Example (5GHz neighbors, specifying filename)> python graph-output.py -f cli_output.txt
Example (5GHz neighbors, specifying SNR of 20) > python cci_finder.py -wlc controller1.nets.net -s 20
Default (if no option specified) is 5Ghz neighbors only and prompting user for controller FQDN & credentials
