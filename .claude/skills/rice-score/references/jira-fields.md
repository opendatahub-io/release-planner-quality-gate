# Jira RICE Field Reference

## Environment Variables

These must be set in the shell environment:
```
JIRA_SERVER=https://redhat.atlassian.net
JIRA_USER=pedouble@redhat.com
JIRA_TOKEN=<api-token>
```

## RICE Custom Field IDs

| Field | ID | Type | Valid Values |
|---|---|---|---|
| Reach | `customfield_10862` | number | 1, 3, 5, 8, 13 |
| Impact | `customfield_10836` | number | 1, 3, 5, 8, 13 |
| Confidence | `customfield_10838` | dropdown | See option IDs below |
| Effort | `customfield_10637` | number | 1, 2, 3, 5, 8, 13 |
| RICE Score | `customfield_10864` | auto-calculated | Do NOT set manually |

## Confidence Dropdown Option IDs

| Display Value | Option ID | JSON Payload |
|---|---|---|
| 100% (High) | 16144 | `{"id":"16144"}` |
| 75% (Medium) | 16145 | `{"id":"16145"}` |
| 50% (Low) | 16146 | `{"id":"16146"}` |

## API Operations

### Fetch a ticket
```bash
curl -s -u "$JIRA_USER:$JIRA_TOKEN" \
  "$JIRA_SERVER/rest/api/3/issue/RHAISTRAT-XXXX?fields=summary,description,status,comment,issuelinks,attachment,issuetype,parent,customfield_10862,customfield_10836,customfield_10838,customfield_10637,customfield_10864"
```

### Search for child tickets
```bash
curl -s -u "$JIRA_USER:$JIRA_TOKEN" "$JIRA_SERVER/rest/api/3/search/jql" \
  -H "Content-Type: application/json" \
  -d '{"jql": "parent = RHAISTRAT-XXXX ORDER BY key ASC", "fields": ["summary","status","issuetype","customfield_10862","customfield_10836","customfield_10838","customfield_10637","customfield_10864"], "maxResults": 50}'
```

### Set RICE scores
```bash
curl -s -u "$JIRA_USER:$JIRA_TOKEN" -X PUT \
  "$JIRA_SERVER/rest/api/3/issue/RHAISTRAT-XXXX" \
  -H "Content-Type: application/json" \
  -d '{"fields":{
    "customfield_10862": REACH_VALUE,
    "customfield_10836": IMPACT_VALUE,
    "customfield_10838": {"id":"CONFIDENCE_OPTION_ID"},
    "customfield_10637": EFFORT_VALUE
  }}'
```

### Download attachment
```bash
curl -s -u "$JIRA_USER:$JIRA_TOKEN" \
  "$JIRA_SERVER/rest/api/3/attachment/content/{attachmentId}" -L
```

### Post justification comment (ADF format)
```bash
curl -s -u "$JIRA_USER:$JIRA_TOKEN" -X POST \
  "$JIRA_SERVER/rest/api/3/issue/RHAISTRAT-XXXX/comment" \
  -H "Content-Type: application/json" \
  -d '{"body":{"type":"doc","version":1,"content":[
    {"type":"heading","attrs":{"level":3},"content":[
      {"type":"text","text":"RICE SCORE JUSTIFICATION:","marks":[{"type":"strong"}]}
    ]},
    {"type":"paragraph","content":[{"type":"text","text":"JUSTIFICATION_TEXT"}]}
  ]}}'
```

## Applicable Projects

RICE scoring fields are available on:
- **RHAISTRAT** — Red Hat AI Strategy features
- **RHOAISTRAT** — Red Hat OpenShift AI Strategy features

These are Feature-level tickets (hierarchy level 2). Outcomes (level 3) and Epics/Stories below do not have RICE fields.

## Important Notes

- Use Jira REST API v3 only. v2 search is removed.
- Search uses POST to `/rest/api/3/search/jql`, not GET.
- Do NOT use Playwright/browser for Jira — always use the API.
- Comments must use ADF (Atlassian Document Format), not plain text.
- The RICE Score field is auto-calculated — never set it directly.
- After setting scores, re-fetch the ticket to verify the auto-calculated score matches your expected calculation.
