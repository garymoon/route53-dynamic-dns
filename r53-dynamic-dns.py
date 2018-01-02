#!/usr/bin/env python3

import socket
import sys
import time
import boto3
import logging
import os
import json
from time import sleep
from urllib import request
from datetime import datetime
from string import Template

DIR = os.path.dirname(os.path.realpath(__file__))
CONFIG = json.load(open(os.path.join(DIR, 'config.json')))

EMAIL_TEMPLATE = Template(
'''Howdy!

Your dynamic DNS entry for "$subdomain.$domain" has changed from "$oldip" to "$newip" at $datetime UTC.

Ciao!
''')

logging.basicConfig(level=logging.INFO, format='%(asctime)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

def get_ip():
  for url in CONFIG['get_ip_urls']:
    try:
      logging.info('Trying {}'.format(url))
      req = request.Request(url)
      req.add_header('User-Agent', 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:26.0) Gecko/20100101 Firefox/26.0')
      response = request.urlopen(req).read().decode("utf-8").strip()
      logging.info('Received "{}"'.format(response))
      socket.inet_aton(response)
      logging.info('"{}" is a valid IPv4 address'.format(response))
      return response
    except:
      #raise #uncomment for debugging
      pass

logging.info('Start')
logging.info('Getting external IP')

external_ip = get_ip()

if (not external_ip):
  logging.info('Unable to get external IP')
  sys.exit(1)

r53 = boto3.client(
    'route53',
    aws_access_key_id=CONFIG['aws_key_id'],
    aws_secret_access_key=CONFIG['aws_key_secret']
)

response = r53.list_resource_record_sets(
    HostedZoneId=CONFIG['zone_id'],
    StartRecordName='{}.{}'.format(CONFIG['subdomain'], CONFIG['domain']),
    StartRecordType='A'
)

old_ip = ''

try:
  old_ip = response.get('ResourceRecordSets')[0]['ResourceRecords'][0]['Value']
except:
  pass

if (not old_ip):
  logging.info('Record does not yet exist, proceeding with creation')
else:
  logging.info('Record currently set to "{}"'.format(old_ip))

if (old_ip != external_ip):
  logging.info('"{}" does not match "{}", proceeding with update'.format(old_ip, external_ip))
else:
  logging.info('"{}" matches "{}", exiting'.format(old_ip, external_ip))
  sys.exit(0)

change = r53.change_resource_record_sets(
  HostedZoneId=CONFIG['zone_id'],
  ChangeBatch={
    'Changes': [{
      'Action': 'UPSERT',
      'ResourceRecordSet': {
        'Name': '{}.{}'.format(CONFIG['subdomain'], CONFIG['domain']),
        'Type': 'A',
        'TTL': CONFIG['ttl'],
        'ResourceRecords': [{
          'Value': external_ip
        }]
      }
    }]
  }
)

change_id = change['ChangeInfo']['Id']

while change['ChangeInfo']['Status'] != 'INSYNC':
  logging.info('Waiting {}s for change "{}"'.format(CONFIG['update_wait_secs'], change_id))
  sleep(CONFIG['update_wait_secs'])
  change = r53.get_change(Id=change_id)

logging.info('Change "{}" is of status "{}"'.format(change_id, change['ChangeInfo']['Status']))

ses = boto3.client('ses',
  region_name=CONFIG['aws_region'],
  aws_access_key_id=CONFIG['aws_key_id'],
  aws_secret_access_key=CONFIG['aws_key_secret']
)

logging.info('Sending notification')

response = ses.send_email(
  Destination={
    'ToAddresses': [
      CONFIG['to_address'],
    ],
  },
  Message={
    'Body': {
      'Text': {
        'Charset': 'UTF-8',
        'Data': EMAIL_TEMPLATE.substitute(subdomain=CONFIG['subdomain'], domain=CONFIG['domain'], oldip=old_ip, newip=external_ip, datetime=datetime.utcnow()),
      },
    },
    'Subject': {
      'Charset': 'UTF-8',
      'Data': CONFIG['subject'],
    },
  },
  Source=CONFIG['from_address'],
)

logging.info('Email sent: {}'.format(response['ResponseMetadata']['RequestId']))

logging.info('Update complete')
