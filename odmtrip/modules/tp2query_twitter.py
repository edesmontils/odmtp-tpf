from rdflib import URIRef, Literal, Namespace, BNode, RDF, XSD
from urllib import urlencode

from utils.twitter_api import TwitterApi
from odmtrip.modules.tp2query import Tp2Query


TWEET_SEARCH = "search/tweets.json"
TWEET_LOOKUP = "statuses/show/%s.json"

# Associate key of the JSON result set with twitter query operators.
# see https://dev.twitter.com/rest/public/search
TWITTER_OPERATORS = {
    '$.text': '"%s"',
    '$.entities.hashtags.*.text': '#%s',
    '$.entities.urls.*.expanded_url': 'url:%s',
    '$.entities.user_mention[0].screen_name': 'from:%s'
}

BASE_QUERY = 'politics filter:safe'

TWEETS_PER_PAGE = 25

TPF_URL = 'http://127.0.0.1:8000/'


class Tp2QueryTwitter(Tp2Query):

    def request(self, tpq, reduced_mapping, fragment):
        last_result = False
        result_set = None
        query_parameters = {}
        twitter = TwitterApi()
        for subject_prefix in reduced_mapping.logical_sources:
            if tpq.subject is None or tpq.subject.startswith(subject_prefix):
                query_url = reduced_mapping.logical_sources[subject_prefix]['query']
        if tpq.subject:
            tweet_id = tpq.subject.rpartition('/')[2]
            query_url = "%s%s" % (query_url, TWEET_LOOKUP % tweet_id)
            result_set = twitter.request(query_url)
            result_set = "[%s]" % result_set
            last_result = True
        else:
            q = BASE_QUERY
            if tpq.obj:
                if tpq.predicate:
                    for s, p, o in reduced_mapping.mapping:
                        if '%s' % o in TWITTER_OPERATORS:
                            q = "%s %s" % (q, TWITTER_OPERATORS['%s' % o] % '%s' % tpq.obj)
                else:
                    q = "%s %s" % (q, '"%s"' % tpq.obj)
            query_parameters['q'] = q
            query_parameters['count'] = TWEETS_PER_PAGE
            query_url = "%s%s" % (query_url, TWEET_SEARCH)
            parameters = "?%s" % urlencode(query_parameters)
            for i in range(tpq.page - 1):
                result_set = twitter.request("%s%s" % (query_url, parameters))
                if 'next_results' in result_set['search_metadata']:
                    parameters = result_set['search_metadata']['next_results']
                else:
                    last_result = True
                    break
            result_set = result_set['statuses']
            # a changer !!!!! total number of results ?????
            nb_results = 40
            self._frament_fill_meta(tpq, fragment, last_result, nb_results, TWEETS_PER_PAGE * len(reduced_mapping.mapping))
        return result_set

    def _frament_fill_meta(self, tpq, fragment, last_result, nb_results, max_triples_per_pages):
        meta_graph = self._tpf_uri('metadata')
        fragment.add_graph(meta_graph)
        source = self._tpf_uri()
        dataset_base = self._tpf_uri()
        dataset_template = Literal('%s%s' % (dataset_base, '{?subject,predicate,object}'))
        data_graph = self._tpf_uri('dataset')
        tp_node = BNode('triplePattern')
        subject_node = BNode('subject')
        predicate_node = BNode('predicate')
        object_node = BNode('object')
        HYDRA = Namespace("http://www.w3.org/ns/hydra/core#")
        VOID = Namespace("http://rdfs.org/ns/void#")
        FOAF = Namespace("http://xmlns.com/foaf/0.1/")
        DCTERMS = Namespace("http://purl.org/dc/terms/")

        fragment.add_meta_quad(meta_graph, FOAF['primaryTopic'], dataset_base, meta_graph)
        fragment.add_meta_quad(self._tpf_uri('dataset'), HYDRA['member'], data_graph, meta_graph)
        fragment.add_meta_quad(data_graph, RDF.type, VOID['Dataset'], meta_graph)
        fragment.add_meta_quad(data_graph, RDF.type, HYDRA['Collection'], meta_graph)
        fragment.add_meta_quad(data_graph, VOID['subset'], source, meta_graph)
        fragment.add_meta_quad(data_graph, VOID['subset'], dataset_base, meta_graph)
        fragment.add_meta_quad(data_graph, VOID['uriLookupEndpoint'], dataset_template, meta_graph)
        fragment.add_meta_quad(data_graph, HYDRA['search'], tp_node, meta_graph)
        fragment.add_meta_quad(tp_node, HYDRA['template'], dataset_template, meta_graph)
        fragment.add_meta_quad(tp_node, HYDRA['variableRepresentation'], HYDRA['ExplicitRepresentation'], meta_graph)
        fragment.add_meta_quad(tp_node, HYDRA['mapping'], subject_node, meta_graph)
        fragment.add_meta_quad(tp_node, HYDRA['mapping'], predicate_node, meta_graph)
        fragment.add_meta_quad(tp_node, HYDRA['mapping'], object_node, meta_graph)
        fragment.add_meta_quad(subject_node, HYDRA['variable'], Literal("subject"), meta_graph)
        fragment.add_meta_quad(subject_node, HYDRA['property'], RDF.subject, meta_graph)
        fragment.add_meta_quad(predicate_node, HYDRA['variable'], Literal("predicate"), meta_graph)
        fragment.add_meta_quad(predicate_node, HYDRA['property'], RDF.predicate, meta_graph)
        fragment.add_meta_quad(object_node, HYDRA['variable'], Literal("object"), meta_graph)
        fragment.add_meta_quad(object_node, HYDRA['property'], RDF.object, meta_graph)

        fragment.add_meta_quad(dataset_base, VOID['subset'], source, meta_graph)
        fragment.add_meta_quad(source, RDF.type, HYDRA['PartialCollectionView'], meta_graph)
        fragment.add_meta_quad(source, DCTERMS['title'], Literal("TPF Twitter search API 1.1"), meta_graph)
        fragment.add_meta_quad(source, DCTERMS['description'], Literal("Triple Pattern from the twitter api matching the pattern {?s=%s, ?p=%s, ?o=%s}" % (tpq.subject, tpq.predicate, tpq.obj)), meta_graph)
        fragment.add_meta_quad(source, DCTERMS['source'], data_graph, meta_graph)
        fragment.add_meta_quad(source, HYDRA['totalItems'], Literal(nb_results, datatype=XSD.int), meta_graph)
        fragment.add_meta_quad(source, VOID['triples'], Literal(nb_results, datatype=XSD.int), meta_graph)
        fragment.add_meta_quad(source, HYDRA['itemsPerPage'], Literal(max_triples_per_pages, datatype=XSD.int), meta_graph)
        fragment.add_meta_quad(source, HYDRA['first'], self._tpf_url(dataset_base, 1, tpq.subject, tpq.predicate, tpq.obj), meta_graph)
        if tpq.page > 1:
            fragment.add_meta_quad(source, HYDRA['previous'], self._tpf_url(dataset_base, tpq.page - 1, tpq.subject, tpq.predicate, tpq.obj), meta_graph)
        if not last_result:
            fragment.add_meta_quad(source, HYDRA['next'], self._tpf_url(dataset_base, tpq.page + 1, tpq.subject, tpq.predicate, tpq.obj), meta_graph)
        fragment.add_prefix('twittertpf', Namespace("%s#" % TPF_URL[:-1]))
        fragment.add_prefix('void', VOID)
        fragment.add_prefix('foaf', FOAF)
        fragment.add_prefix('hydra', HYDRA)
        fragment.add_prefix('purl', Namespace('http://purl.org/dc/terms/'))

    def _tpf_uri(self, tag=None):
        if tag is None:
            return URIRef(TPF_URL)
        return URIRef("%s%s" % (TPF_URL[:-1], '#%s' % tag))

    def _tpf_url(self, dataset_base, page, subject, predicate, obj):
        subject_parameter = subject if subject else ''
        predicate_parameter = predicate if predicate else ''
        object_parameter = ('"%s"^^%s' % (obj, obj._datatype)) if obj else ''
        parameters = {'page': page, 'subject': subject_parameter, 'predicate': predicate_parameter, 'object': object_parameter}
        return URIRef("%s?%s" % (dataset_base, urlencode(parameters)))