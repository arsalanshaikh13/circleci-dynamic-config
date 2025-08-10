#!/usr/bin/env python3

import datetime
from yaml import dump

current_time = datetime.datetime.now()
weekday = current_time.weekday() < 5

no_deploy = (current_time.weekday() < 5) and (current_time.hour() > 3) and (current_time.hour < 20)
#no_deploy = False
weekday = True
no_deploy = True;
config = {
"version": 2.1,
"jobs": {
  "build": {
    "docker": [
      {
        "image": "ubuntu:14.04"
      }
    ],
    "steps": [
      "checkout",
        {
          "run": 
            {
              "command": 'echo "Config API works!"'
            }
        } 
      ]
    }
  },
  "workflows": {
    "build-server": {
      "jobs": [
          "build"
      ]
    }
  }
}
if weekday:
    config["jobs"]["weekday"] = {
      "docker" : [
        {
          "image": "ubuntu:14.04"
        }
      ],
      "steps": [
        "checkout",
          {
            "run": {
              "command": 'echo "This is a weekday job!"'
          }
        }
      ]
  }
    config["workflows"]["build-server"]["jobs"].append(
        {"weekday_job": {"requires": ["build"]}}
    )
  
if no_deploy:
    config["workflows"]["build-server"]["jobs"][0] = {"build": {"requires":["hold"]}}
    config["workflows"]["build-server"]["jobs"].append({"hold": {"type": "approval"}})
print(dump(config))