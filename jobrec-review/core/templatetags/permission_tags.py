from django import template
from core.auth_utils import has_perm

register = template.Library()

@register.filter
def has_perm_tag(user, codename):
    return has_perm(user, codename)


@register.filter
def strip_page(query_dict):
    qd = query_dict.copy()
    for key in list(qd.keys()):
        if key in ('page', 'incoming_page', 'outgoing_page'):
            del qd[key]
    return qd.urlencode()
