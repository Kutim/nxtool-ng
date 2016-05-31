import logging

import collections

try:
    from itertools import zip_longest as izip_longest
except ImportError:  # python 2
    from itertools import izip_longest

from . import modify_search
from nxapi import whitelist


def __guess_prefixes(strings):
    """ Get the list of the most common prefixes for `strings`.
    Careful, this function is a bit fucked up, with stupid complexity,
    but since our dataset is small, who cares?

    :param list of list of str strings: [['wp-content', '10'], ['pouet', pif']]
    :return dict: {url1:nb_url1, url2: nb_url2, ...}
    """
    if len(strings) < 2:
        return {strings: 1}

    threshold = len(strings)
    prefix, prefixes = [], []
    for chars in izip_longest(*strings, fillvalue=''):
        char, count = collections.Counter(chars).most_common(1)[0]
        if count == 1:
            break
        elif count < threshold:
            if prefix:
                prefixes.append(('/' + ''.join(prefix), threshold))
            threshold = count
        prefix.append(char)
    if prefix:
        prefixes.append(('/' + ''.join(prefix), threshold))
    return prefixes


@modify_search
def generate_whitelist(provider, whitelists):
    provider.add_filters({'zone': 'URL', 'id': '1002'})

    uris = provider._get_top('uri')
    if not uris:
        return []

    # Filter already whitelisted things
    already_whitelisted_uri = set()
    for _, _, r in map(whitelist.parse, whitelists):
        if 'URL' in r['mz'] and 1002 in r['wl']:
            already_whitelisted_uri.union(r['mz'])
    uris = {nb: uri for (nb, uri) in uris.items() if uri not in already_whitelisted_uri}  # TODO less stoopid filtering

    if not uris:
        return []

    prefixes = __guess_prefixes([a.split('/')[1:] for a in uris.values()])

    # We multiply the number of common paths between url with the number
    # of times the url has been triggered by an exception.
    best_path = collections.defaultdict(int)
    for pre, nb_pre in prefixes:
        for nb, uri in uris.items():
            if uri.startswith(pre):
                best_path[pre] += int(nb) * nb_pre

    rules = []
    for url, nb in best_path.items():
        logging.info('The url "%s" triggered %d exceptions for the rule 1002, whitelisting it.' % (url, nb))
        rules.append('BasicRule wl:1002 "mz:$URL_X:^%s|URL";' % url)
    return rules