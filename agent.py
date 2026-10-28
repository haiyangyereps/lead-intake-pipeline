import argparse,json
from pathlib import Path
from agent_runtime import Provider,FixtureProvider,Journal,tool,run_agent,load_config
TEXT={'type':'string'}

def main():
 p=argparse.ArgumentParser();p.add_argument('--config');p.add_argument('--prompt',default=DEFAULT_PROMPT);p.add_argument('--journal',default='agent-journal.db');p.add_argument('--source',default=DEFAULT_SOURCE);p.add_argument('--fixture',action='store_true');p.add_argument('--output',default='agent-result.json');p.add_argument('--review');p.add_argument('--reviewer');p.add_argument('--decision',choices=['approved','rejected']);a=p.parse_args()
 if a.config:load_config(a.config)
 j=Journal(a.journal)
 if a.review:
  if not a.reviewer or not a.decision:p.error('reviewer and decision required')
  print(json.dumps(j.review(a.review,a.reviewer,a.decision)));return
 tools,handlers,steps=configure(a.source,j)
 provider=FixtureProvider(steps) if a.fixture else Provider()
 result=run_agent(provider,j,a.prompt,tools,handlers,POLICY,mode='scripted_fixture' if a.fixture else 'live_model')
 Path(a.output).write_text(json.dumps(result,indent=2,ensure_ascii=False));print(json.dumps({'run_id':result['id'],'mode':result['mode'],'status':result['status'],'output':a.output}))

import operations
DEFAULT_SOURCE='agent-leads.db'
DEFAULT_PROMPT='Review open leads and propose the most useful follow-up. Do not contact anyone.'
POLICY='You are a lead operations assistant. Query leads before proposing work. Scores are business rules, not conversion probabilities. Do not claim revenue from potential value.'
def configure(source,j):
 db=operations.connect(source)
 if not db.execute('SELECT COUNT(*) FROM opportunities').fetchone()[0]:operations.seed(db)
 def lookup(a,r):
  return [{k:v for k,v in x.items() if k not in ('email','name')} for x in operations.dashboard(db)['leads'] if x['stage'] not in ('won','lost')]
 def propose(a,r):
  row=db.execute('SELECT * FROM opportunities WHERE lead_id=?',(a['lead_id'],)).fetchone()
  if not row:raise ValueError('Unknown lead')
  if row['stage'] in ('won','lost'):raise ValueError('Lead is closed')
  return j.propose(r,{'kind':'follow_up_task','lead_id':a['lead_id'],'source_version':row['version'],'recommendation':a['recommendation']})
 tools=[tool('list_open_leads','Read current lead status, priority, owner and follow-up information',{}),tool('propose_follow_up','Queue an internal follow-up suggestion for human review',{'lead_id':{'type':'integer'},'recommendation':TEXT})]
 return tools,{'list_open_leads':lookup,'propose_follow_up':propose},[('list_open_leads',{}),('propose_follow_up',{'lead_id':1,'recommendation':'Assign an owner and review the overdue enquiry before preparing a response.'}),'SCRIPTED FIXTURE: Lead 1 has a pending follow-up suggestion. No customer message was sent.']

if __name__=='__main__':main()
