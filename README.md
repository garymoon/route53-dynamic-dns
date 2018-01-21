# Route 53 Dynamic DNS

`r53-dynamic-dns.py` is run as a cronjob. Each run it will collect the external IP address of the machine it's running on and, when necessary, update a route53 record to point to it. When a change takes place it will send a notification email.

### Requirements
* Python 3
* boto3

### Setup
1. Set up your hosted zone in Route53.
2. Set up a domain for email sending in SES, and validate the receiving address.
3. Create a programmatic-access IAM user with the policy in `iam_policy.json`, substituting the zone ID and to-address.
4. Create a `config.json` from the `config.sample.json`.
5. Create a cronjob that runs the script at regular intervals. With infrequent updates, the script will be free to run if it runs once an hour. E.g. `17 * * * * nobody python3 /opt/route53-dynamic-dns/r53-dynamic-dns.py`

### Notes
* Unfortunately the IAM policy cannot be locked down to a specific resource record, so make sure that the domain you're using is unimportant.
* The get-IP URLs are checked in order, so start with the most reliable to keep requests to a minimum. Any site in the list must return just an IP address, nothing more. There are a number of other options if you're willing to forgo TLS.
* The script will exit with status code 1 if it fails. All output is to stdout.
* The logging is relatively verbose, so you can see it work as it goes.
* The script will wait for the change to complete, polling every `update_wait_secs`, before exiting.
* As a backup plan, you can consider maintaining a reverse SSH tunnel with something like this: `autossh -M 0 -N -R 22000:127.0.0.1:22 -g -o ServerAliveInterval=60 -o BatchMode=yes -i [key] [user]@[host]`. There are a number of examples around the interwebs for using init.d/inittab, upstart or systemd to monitor the tunnel for you.
