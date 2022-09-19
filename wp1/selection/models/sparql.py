import json
from pyparsing.exceptions import ParseException
import requests
from rdflib.term import Literal, URIRef, Variable
from rdflib.plugins.sparql import algebra
from rdflib.plugins.sparql import parser
from rdflib.plugins.sparql.parserutils import CompValue

from wp1.constants import WIKIDATA_PREFIXES, WP1_USER_AGENT
from wp1.selection.abstract_builder import AbstractBuilder


class Builder(AbstractBuilder):

  def instrument_query(self, a, query_variable=None):
    '''
    Takes a SPARQL query, and adds a binding for Wikipedia article names.

    Given a pre-parsed SPARQL Algebra 'a' (from the rdflib sparql library), this method
    adds a variable to the SELECT clause, '_wp1_0'. It also adds an OPTIONAL (LEFT JOIN)
    binding for this variable, such that the variable is bound to the English Wikipedia
    URL of the main subject of the query (which is derived from the 'query_variable'
    parameter). When the instrumented query is sent to the Wikidata SPARQL endpoint,
    the values of '_wp1_0' are the primary data that is retrieved.

    Modifies the algebra 'a' in place. No return value.

    Note: this is only designed to work on SELECT queries and will likely have
    undefined behavior for anything else.
    '''
    if not query_variable:
      query_variable = 'article'
    else:
      query_variable = query_variable.lstrip('?')

    def modify_query_in_place(node):
      if getattr(node, 'name', None) == 'Project':
        node.PV.append(Variable('_wp1_0'))
      elif getattr(node, 'name', None) == 'BGP':
        if not node.triples:
          return
        p1 = node
        p2_vars = set((Variable('_wp1_0'), Variable(query_variable)))
        p2 = CompValue('BGP',
                       _vars=p2_vars,
                       triples=[(Variable('_wp1_0'),
                                 URIRef('http://schema.org/inLanguage'),
                                 Literal('en')),
                                (Variable('_wp1_0'),
                                 URIRef('http://schema.org/isPartOf'),
                                 URIRef('https://en.wikipedia.org/')),
                                (Variable('_wp1_0'),
                                 URIRef('http://schema.org/about'),
                                 Variable(query_variable))])
        total_vars = node._vars.union(p2_vars)
        join = CompValue('LeftJoin', _vars=total_vars, p1=p1, p2=p2)
        return join

    algebra.traverse(a, visitPre=modify_query_in_place)

  def extract_article(self, url):
    return url.split('/')[-1]

  def build(self, content_type, **params):
    if content_type != 'text/tab-separated-values':
      raise ValueError('Unrecognized content type')

    query_variable = params.get('queryVariable')
    parse_results = parser.parseQuery(params['query'])
    query = algebra.translateQuery(parse_results, initNs=WIKIDATA_PREFIXES)
    self.instrument_query(query.algebra, query_variable)
    modified_query = algebra.translateAlgebra(query)

    r = requests.post('https://query.wikidata.org/sparql',
                      headers={'User-Agent': WP1_USER_AGENT},
                      data={
                          'query': modified_query,
                          'format': 'json',
                      })
    r.raise_for_status()

    if len(r.content) > 1024 * 1024 * 10:
      raise ValueError('Response was larger than 10 MB')

    try:
      data = r.json()
    except json.decoder.JSONDecodeError:
      raise ValueError('Response was not valid JSON')

    urls = [
        d['_wp1_0']['value']
        for d in data['results']['bindings']
        if '_wp1_0' in d
    ]
    articles = [self.extract_article(url) for url in urls]

    return '\n'.join(articles).encode('utf-8')

  def validate(self, **params):
    try:
      parse_results = parser.parseQuery(params['query'])
    except ParseException as pe:
      # The query cannot be parsed as SPARQL, invalid syntax.
      return ('', params['query'],
              ['Could not parse query, are you sure it\'s valid SPARQL?'])

    try:
      query = algebra.translateQuery(parse_results, initNs=WIKIDATA_PREFIXES)
    except Exception as e:
      # In testing, this was most common when the query contained
      # an undefined prefix.
      return ('', params['query'], [e.args[0]])

    return ('', '', [])
