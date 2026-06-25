import sys
sys.path.append('src')
from career_tracker.graph.workflow import build_workflow, run_workflow

workflow = build_workflow()
iters = 0
attempted = set()
while iters < 10:
    res = run_workflow(workflow, thread_id='manual_run_loop', log_fn=lambda x: None)
    iters += 1
    
    curr_email = res.get('current_email', {})
    if curr_email:
        msg_id = curr_email.get('message_id')
        if msg_id in attempted:
            break
        attempted.add(msg_id)
        
    stats = res.get('fetch_stats') or {}
    if not res.get('should_continue') or not stats.get('new_emails'):
        break
