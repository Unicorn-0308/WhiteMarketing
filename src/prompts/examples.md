# Example MongoDB datas
- Task
  ```json
  {
    "gid": "1210364361403311",
    "actual_time_minutes": null,
    "assignee": {
      "gid": "1205300173907735",
      "name": "Michaela Reichert",
      "resource_type": "user"
    },
    "assignee_status": "inbox",
    "completed": false,
    "completed_at": null,
    "created_at": {
      "$date": "2025-05-23T11:43:29.282Z"
    },
    "custom_fields": [
      {
        "gid": "1203189117755373",
        "enabled": true,
        "name": "Est. Time (hours)",
        "description": "",
        "number_value": null,
        "precision": 2,
        "created_by": {
          "gid": "1111867806420435",
          "name": "Roberto",
          "resource_type": "user"
        },
        "display_value": null,
        "resource_subtype": "number",
        "resource_type": "custom_field",
        "is_formula_field": false,
        "is_value_read_only": false,
        "type": "number"
      },
      {
        "gid": "1122053390215334",
        "enabled": true,
        "enum_options": [
          {
            "gid": "1122053390215335",
            "color": "red",
            "enabled": true,
            "name": "High",
            "resource_type": "enum_option"
          },
          {
            "gid": "1122053390215336",
            "color": "yellow-orange",
            "enabled": true,
            "name": "Medium",
            "resource_type": "enum_option"
          },
          {
            "gid": "1122053390215337",
            "color": "yellow",
            "enabled": true,
            "name": "Low",
            "resource_type": "enum_option"
          },
          {
            "gid": "1201149037357068",
            "color": "green",
            "enabled": true,
            "name": "Evergreen",
            "resource_type": "enum_option"
          }
        ],
        "enum_value": null,
        "name": "Priority",
        "description": "",
        "created_by": {
          "gid": "1111867806420435",
          "name": "Roberto",
          "resource_type": "user"
        },
        "display_value": null,
        "resource_subtype": "enum",
        "resource_type": "custom_field",
        "is_formula_field": false,
        "is_value_read_only": false,
        "type": "enum"
      }
    ],
    "due_at": null,
    "due_on": {
      "$date": "2025-05-28T00:00:00.000Z"
    },
    "followers": [
      {
        "gid": "1141817286900230",
        "name": "Stefanie Heise",
        "resource_type": "user"
      },
      {
        "gid": "1205300173907735",
        "name": "Michaela Reichert",
        "resource_type": "user"
      }
    ],
    "hearted": false,
    "hearts": [],
    "liked": false,
    "likes": [],
    "memberships": [
      {
        "project": {
          "gid": "1205292975079160",
          "name": "Michaela",
          "resource_type": "project"
        },
        "section": {
          "gid": "1205292975079161",
          "name": "Untitled section",
          "resource_type": "section"
        }
      },
      {
        "project": {
          "gid": "1205094445372673",
          "name": "009. HelloCash | PPC",
          "resource_type": "project"
        },
        "section": {
          "gid": "1205094445372674",
          "name": "Untitled section",
          "resource_type": "section"
        }
      }
    ],
    "modified_at": {
      "$date": "2025-05-25T19:03:01.933Z"
    },
    "name": "HelloCash Basic Optimization",
    "notes": "Hello 🙂 \n\nHere the tasks would include:\n\nQuick budget check (beginning of June you may ask Miriam for the monthly budgets)\nNegative keywords optimization based on the Search Term results\nImprove account optimization score by going through Google's recommendations apply / dismiss where it makes sense. \n\nThank you!",
    "num_hearts": 0,
    "num_likes": 0,
    "parent": null,
    "permalink_url": "https://app.asana.com/1/1120263180104321/project/1205094445372673/task/1210364361403311",
    "projects": [
      {
        "gid": "1205094445372673",
        "name": "009. HelloCash | PPC",
        "resource_type": "project"
      },
      {
        "gid": "1205292975079160",
        "name": "Michaela",
        "resource_type": "project"
      }
    ],
    "resource_type": "task",
    "start_at": null,
    "start_on": null,
    "tags": [
      {
        "gid": "1210373864089713",
        "name": "Google Search",
        "resource_type": "tag"
      }
    ],
    "resource_subtype": "default_task",
    "workspace": {
      "gid": "1120263180104321",
      "name": "white-consulting.co",
      "resource_type": "workspace"
    },
    "created_by": {
      "gid": "1141817286900230",
      "resource_type": "user"
    },
    "dependencies": [],
    "dependents": [],
    "html_notes": "<body>Hello 🙂 \n\nHere the tasks would include:\n\nQuick budget check (beginning of June you may ask Miriam for the monthly budgets)\nNegative keywords optimization based on the Search Term results\nImprove account optimization score by going through Google's recommendations apply / dismiss where it makes sense. \n\nThank you!</body>",
    "is_rendered_as_separator": false,
    "num_subtasks": 0,
    "from": "Asana",
    "client": [
      "009"
    ],
    "type": "client_spec"
  }
  ```
- Story
  ```json
  {
    "gid": "1206149650313599",
    "created_at": {
      "$date": "2023-12-12T09:37:59.824Z"
    },
    "created_by": {
      "gid": "1141817286900230",
      "name": "Stefanie Heise",
      "resource_type": "user"
    },
    "previews": [],
    "resource_type": "story",
    "source": "web",
    "text": "Stefanie Heise duplicated task from ✓ Weekly Performance Email",
    "type": "client_spec",
    "resource_subtype": "duplicated",
    "target": {
      "gid": "1206149330522575",
      "name": "Weekly Performance Email",
      "resource_type": "task",
      "resource_subtype": "default_task"
    },
    "html_text": "<b><a href=\"https://app.asana.com/0/profile/1141817289473492\">Stefanie Heise</a></b> duplicated task from <a href=\"https://app.asana.com/1/1120263180104321/project/1141793583725140/task/1206109246793879\">✓ Weekly Performance Email</a>",
    "from": "Asana",
    "client": [
      "009"
    ]
  }
  ```
- Attachment
  ```json
  {
    "gid": "1205820868929545",
    "created_at": {
      "$date": "2023-10-30T07:02:11.454Z"
    },
    "download_url": "https://asana-user-private-us-east-1.s3.amazonaws.com/assets/1120263180104321/1205820868929544/4569e7c7948402fc81a3efcedce6e6ee?X-Amz-Security-Token=IQoJb3JpZ2luX2VjEHsaCXVzLWVhc3QtMSJHMEUCIQCIy%2F0RIymM1TfAtSDkyRvsMj6eTJOAht2g%2FlX3iriLeQIgMEi%2FVV29CrkXHEduvMoRla2t6OZlDGfvQozBM1bre9sqlQUIRBAAGgw0MDM0ODM0NDY4NDAiDIeVG0DyQQ1ceCL1YCryBGfBUgyQ9uok%2FIQf%2BOQYiEyOkBXpyZJ6dFN8ZIqXsi2I%2BlbBpnc0aCIOwR4b07w8IFNgRP8fWnEQ%2FNnPZySCSKxqKYBeROV2EPdgkCHR96zWJe4RBDQV4Hs%2BwcT4cpM6tnDVMgnscpPksahXus%2BXP41kiUxmxP9rAajwwUqkCfapH9FyrFiV2feXwkeTPYKlIJ6jTJ9%2Fcz%2FDn1gCkXaRn%2F18SwDyILWiwuxnkT5JoZpbaDCo9QVd9PJy%2BwmytBJ4V0OJ36fiLNpF0aaVN%2B8e%2F%2FeZHA%2Fiy8HDaN22j0iLgeFP8rZEG582cBQn1ivy6GO46fXwl6ua4yqmoteSP5e1CHZ8w3uRcUP%2BezTcAhg8S3%2Bokl0N3ht08hRwi8aBHR1yf6g6RNIuj%2FQ5BGAtu5fvjSC%2F9yabvi%2Fo2f2Z12b2gnX2Mm1PUS1Lm1DEHHZmLcvJ6iU0NDt84NqlF67DpjPej%2B1CTM6%2FD6r3jkcMvsO9yA8s3ZeCu7zlUHln%2BPqFuBvsWVY8K0czzspKWlcnY8MeogmpVpsgxhJzcrbCO6TojGfGtyvUkvICouLUHElY6IlG7YjBRZZf6YpOUk6lif3QxeJxFj6AQXDXQXGw6in85Oc8jQeJ3qkUOz4g1EJJscFClKxqX1tXGIaIBPtkLEqOEflZ%2B6v49uJCHwM0AShPwISkt%2Fy8JMIhrvcY3LOW%2BG8yAPy8bzDHCB77m97zzGD%2Fz353KaOsqIRyOms1T2aQqATCNUnbgGJ31IZZUGdDAIAWvylSwMzKFUNqtSnk%2B89FRFZep3nd8er7k0PMmQzNkP08b90%2FCcHlqJte%2BGXhxUlupdXyMLOE0cEGOpsBilVnaFeBupXS385U58eXwbx3EwMlNWZurdnG5bTCpiNCeXaHNn4%2Fwfcmxuc%2Bh5y1kiMyyo8yCNcCS1zXtmhb4FLis2DLmm3VT%2BSN9kxgw%2F0ibwWatufUbnEwWBJ98i68ix5YwCuKRfqao2gkD9F%2F5KOnqhlvmopIxIXfUbH3aRhZDmiqQEnt6Xynx3XSmMh%2Bl7xEk6VNXTB%2BWls%3D&X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Date=20250526T140955Z&X-Amz-SignedHeaders=host&X-Amz-Credential=ASIAV34L4ZY4LODVWWC6%2F20250526%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Expires=1800&X-Amz-Signature=f4720f9839bae186c44670e81f2d5b3290fad98419a5335ab8b6539f9383bf7d#_=_",
    "host": "asana",
    "name": "fb-ad-kassensystem-carousel-friseur (1).jpg",
    "parent": {
      "gid": "1205782812785624",
      "name": "HelloCash FB Add Beauty Creatives",
      "resource_type": "task",
      "resource_subtype": "default_task"
    },
    "permanent_url": "https://app.asana.com/app/asana/-/get_asset?asset_id=1205820868929545",
    "resource_type": "attachment",
    "resource_subtype": "asana",
    "view_url": "https://asana-user-private-us-east-1.s3.amazonaws.com/assets/1120263180104321/1205820868929544/4569e7c7948402fc81a3efcedce6e6ee?X-Amz-Security-Token=IQoJb3JpZ2luX2VjEHsaCXVzLWVhc3QtMSJHMEUCIQCIy%2F0RIymM1TfAtSDkyRvsMj6eTJOAht2g%2FlX3iriLeQIgMEi%2FVV29CrkXHEduvMoRla2t6OZlDGfvQozBM1bre9sqlQUIRBAAGgw0MDM0ODM0NDY4NDAiDIeVG0DyQQ1ceCL1YCryBGfBUgyQ9uok%2FIQf%2BOQYiEyOkBXpyZJ6dFN8ZIqXsi2I%2BlbBpnc0aCIOwR4b07w8IFNgRP8fWnEQ%2FNnPZySCSKxqKYBeROV2EPdgkCHR96zWJe4RBDQV4Hs%2BwcT4cpM6tnDVMgnscpPksahXus%2BXP41kiUxmxP9rAajwwUqkCfapH9FyrFiV2feXwkeTPYKlIJ6jTJ9%2Fcz%2FDn1gCkXaRn%2F18SwDyILWiwuxnkT5JoZpbaDCo9QVd9PJy%2BwmytBJ4V0OJ36fiLNpF0aaVN%2B8e%2F%2FeZHA%2Fiy8HDaN22j0iLgeFP8rZEG582cBQn1ivy6GO46fXwl6ua4yqmoteSP5e1CHZ8w3uRcUP%2BezTcAhg8S3%2Bokl0N3ht08hRwi8aBHR1yf6g6RNIuj%2FQ5BGAtu5fvjSC%2F9yabvi%2Fo2f2Z12b2gnX2Mm1PUS1Lm1DEHHZmLcvJ6iU0NDt84NqlF67DpjPej%2B1CTM6%2FD6r3jkcMvsO9yA8s3ZeCu7zlUHln%2BPqFuBvsWVY8K0czzspKWlcnY8MeogmpVpsgxhJzcrbCO6TojGfGtyvUkvICouLUHElY6IlG7YjBRZZf6YpOUk6lif3QxeJxFj6AQXDXQXGw6in85Oc8jQeJ3qkUOz4g1EJJscFClKxqX1tXGIaIBPtkLEqOEflZ%2B6v49uJCHwM0AShPwISkt%2Fy8JMIhrvcY3LOW%2BG8yAPy8bzDHCB77m97zzGD%2Fz353KaOsqIRyOms1T2aQqATCNUnbgGJ31IZZUGdDAIAWvylSwMzKFUNqtSnk%2B89FRFZep3nd8er7k0PMmQzNkP08b90%2FCcHlqJte%2BGXhxUlupdXyMLOE0cEGOpsBilVnaFeBupXS385U58eXwbx3EwMlNWZurdnG5bTCpiNCeXaHNn4%2Fwfcmxuc%2Bh5y1kiMyyo8yCNcCS1zXtmhb4FLis2DLmm3VT%2BSN9kxgw%2F0ibwWatufUbnEwWBJ98i68ix5YwCuKRfqao2gkD9F%2F5KOnqhlvmopIxIXfUbH3aRhZDmiqQEnt6Xynx3XSmMh%2Bl7xEk6VNXTB%2BWls%3D&X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Date=20250526T140955Z&X-Amz-SignedHeaders=host&X-Amz-Credential=ASIAV34L4ZY4LODVWWC6%2F20250526%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Expires=1800&X-Amz-Signature=f4720f9839bae186c44670e81f2d5b3290fad98419a5335ab8b6539f9383bf7d#_=_",
    "from": "Asana",
    "client": [
      "009"
    ],
    "type": "client_spec"
  }
  ```
- Slite note
  ```json
  {
    "id": "Fg6D_xHyF2rdUd",
    "attributes": {
      "date": "2023-12-04",
      "tags": "Google Search, Facebook Ads",
      "owner": "@Stefanie Heise"
    },
    "children": [],
    "client": [
      "009"
    ],
    "content": "> **Consultants: **@Stefanie Heise  \n> ****\\*\\*****Project Leader:\\*\\* @Nina Mavali\n\n## ⏪ Retro\n\n### Actions Taken\n\n**Google Ads DE:**\n\nPaused low quality/low search volume keywords in:\n\n- GER-DE-G-S[Cat_01]: Registrierkasse\n- GER-DE-G-S[Cat_01|Attr_02]: Registrierkasse Pflicht\n- GER-DE-G-S[Cat_01|Attr_03]: Registrierkasse Kaufen\n- GER-DE-G-S[Cat_01|Attr_03]: Registrierkasse Shops\n- GER-DE-G-S[Cat_02|Biz_01]: Kassensysteme Gastronomie\n- GER-DE-G-S[Cat_03]: Kasse\n\nImproved Ad Strength from Poor/Average to Good/Excellent:\n\n- GER-DE-G-S[Cat_02]: Kassensysteme\n- GER-DE-G-S[Cat_08]: Kostenlos\n- GER-DE-G-S[Cat_03]: Kasse\n- GER-DE-G-S[Cat_12]: Beauty und Friseursalon\n\n**Google Ads AT:**\n\nPaused low quality/low search volume keywords in:\n\n- AT-DE-G-S[Cat_05|Other_05]: Kasse Device\n- AT-DE-G-S[Cat_05|Biz_01]: Kasse Einzelhandel\n- AT-DE-G-S[Cat_01]: Registrierkasse\n- AT-DE-G-S[Cat_01|Other_01]: Registrierkasse Generic\n- AT-DE-G-S[Cat_05]: Kasse POS\n- AT-DE-G-S[Cat_08|Attr_04]: Kassensoftware Kostenlos\n\nImproved Ad Strength from Poor/Average to Good/Excellent:\n\n- AT-DE-G-S[Cat_01|Dev_02]: Registrierkasse App\n- AT-DE-G-S[Cat_01|Attr_07]: Registrierkasse Selber Programmieren\n\n## 📊 Data\n\n- <u>Google DE:</u> 128 registrations at €40\n- <u>Google AT:</u> 58 registrations at €33\n- <u>Bing DE: </u> 7 registrations at €29\n- <u>Bing AT:</u> 5 registrations at €29\n\n## ⏩ Next Steps\n\n-\n",
    "date": {
      "$date": "2023-12-04T00:00:00.000Z"
    },
    "from": "Slite",
    "parentNoteId": "ow9OJ5mJo6YtFq",
    "title": "HelloCash 04/12/2023 - Weekly Update",
    "type": "weekly",
    "updatedAt": {
      "$date": "2025-05-25T18:29:17.604Z"
    },
    "url": "https://whitemarketing.slite.com/api/s/Fg6D_xHyF2rdUd/HelloCash-04-12-2023-Weekly-Update"
  }
  ```