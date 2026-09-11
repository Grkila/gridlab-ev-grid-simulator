"""Focus routing never infers permission to edit from arbitrary prose."""
import re
from mvgrid.novi_sad.playground.agent_contract import WORKFLOWS


def route_request(message, requested_action='auto', specification_id=None):
    if requested_action not in ('auto',*WORKFLOWS):raise ValueError('Choose a supported chat workflow.')
    if requested_action=='implement':
        if not isinstance(specification_id,str) or not re.fullmatch(r'strategy-[a-f0-9]{20}',specification_id):
            raise ValueError('Implementation requires a saved specification ID in the chat selector.')
        if re.match(r'^\s*(?:[\'"`]|(?:(?:please|can you|could you|would you|will you|just|only)\s+)*(?:do not|don.t|not|never|explain|what|how|why|plan|describe|quote|summarize)\b)',message,re.I):
            raise ValueError('Message conflicts with implementation mode. Choose a planning/explanation workflow or state the implementation request directly.')
        return 'implement',dict(command='BUILD',based_on=specification_id)
    if specification_id:raise ValueError('A specification ID selector is only used with implementation mode.')
    if requested_action!='auto':return requested_action,None
    if re.match(r'^\s*STRATEGY\s+BUILD(?:\s|$)',message,re.I):return 'implement',message
    # Routing changes guidance only. Ordinary prose never grants workspace writes.
    lower=message.lower()
    if re.match(r'^\s*(?:please\s+)?(?:explain|what|how|why|describe|summarize|plan)\b',lower):return 'explain',None
    if re.search(r'\b(compare|comparison)\b',lower):return 'compare',None
    if re.search(r'\b(diagnose|failure|failed|violation)\b',lower):return 'diagnose',None
    if re.search(r'\b(benchmark|suite)\b',lower):return 'benchmark',None
    if re.search(r'\b(train|training|reinforcement)\b',lower):return 'training',None
    if re.search(r'\b(run|execute|start|cancel|resume)\b',lower):return 'run',None
    if re.search(r'\b(algorithm|strategy|controller|implement|build)\b',lower):return 'algorithm',None
    if re.search(r'\b(scenario|demand|fleet)\b',lower):return 'scenario',None
    if re.search(r'\b(compare|comparison)\b',lower):return 'compare',None
    if re.search(r'\b(diagnose|failure|failed|violation)\b',lower):return 'diagnose',None
    return 'explain',None
