"""Follow visible internal GET links with authenticated disposable test clients."""
from html.parser import HTMLParser
from urllib.parse import urlsplit
from collections import deque


class Links(HTMLParser):
    def __init__(self): super().__init__(); self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag=='a':
            href=dict(attrs).get('href','')
            if href.startswith('/') and not href.startswith('//'): self.links.append(href)


def check_links(flow,ei,starts,max_pages=350):
    todo=deque((path,0) for path in starts); seen=set(); failures=[]
    while todo and len(seen)<max_pages:
        target,depth=todo.popleft(); parsed=urlsplit(target)
        if parsed.path in seen or parsed.path in ('/logout','/ei-lab/logout/') or '/delete' in parsed.path:
            continue
        seen.add(parsed.path)
        client=ei if parsed.path.startswith('/ei-lab/') else flow
        try:
            if parsed.path.startswith('/ei-lab/'):
                local=target[len('/ei-lab'):] or '/'
                response=client.get(local,SCRIPT_NAME='/ei-lab')
            else:
                response=client.get(target)
            status=response.status_code
            if status in (301,302,303,307,308):
                destination=response.headers.get('Location','')
                if 'login' in destination: failures.append((target,status,'unexpected authentication redirect'))
                elif destination.startswith('/'): todo.append((destination,depth))
                continue
            if status>=400:
                failures.append((target,status,'')); continue
            content_type=response.headers.get('Content-Type','')
            if 'text/html' not in content_type or depth>=3: continue
            content=response.get_data(as_text=True) if hasattr(response,'get_data') else response.content.decode('utf8','replace')
            parser=Links(); parser.feed(content)
            todo.extend((href,depth+1) for href in parser.links)
        except Exception as error:
            failures.append((target,type(error).__name__,str(error)[:180]))
    return {'checked':len(seen),'failures':failures,'capped':bool(todo)}
