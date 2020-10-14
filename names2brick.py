from lark import Lark
from rdflib import RDF, Namespace, Graph, Literal, URIRef
import sys
import argparse

argparser = argparse.ArgumentParser(description='Convert data using a BIM and BACnet friendly naming convention to a Brick model')
argparser.add_argument('--namespace', nargs=2, metavar=('prefix', 'fullnamespace'), action='append', default=[], help='RDF namespace for building data. Default is prefix ex and example.com/building#')
argparser.add_argument("input_file", metavar='INPUTFILE', help='Data file to process. One name per line.')
argparser.add_argument("output_file", nargs='?', metavar='OUTPUTFILE', help='TTL file to store results')
arguments = argparser.parse_args()

namespaces = arguments.namespace

prefixes = {
    'brick': 'https://brickschema.org/schema/1.1/Brick#',
    'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'ex': 'https://example.com/building/#'
}

for ns in namespaces:
    prefixes[ns[0]] = ns[1]

input_file = arguments.input_file
g = Graph()
BRICK = Namespace('https://brickschema.org/schema/1.1/Brick#')
if len(namespaces):
    EX = Namespace(namespaces[0][1])
else:
    EX = Namespace('https://example.com/building/#')

for pfx, ns in prefixes.items():
    g.bind(pfx, ns)

#
# Figure out how to decode relationships
# if not explicitly told
# really only to disambiguate between
# x/y - does the slash mean 
# x isLocationOf y, 
# x hasPart y, 
# x hasPoint y?
# first element is x, second is y
#
rules = {
  ('LOCATION', 'LOCATION'): BRICK.hasPart,
  ('LOCATION', 'EQUIPMENT'): BRICK.isLocationOf,
  ('LOCATION', 'POINT'): BRICK.isLocationOf,
  ('POINT', 'LOCATION'): BRICK.hasLocation,
  ('POINT', 'EQUIPMENT'): BRICK.isPointOf,
  ('EQUIPMENT', 'POINT'): BRICK.hasPoint,
  ('EQUIPMENT', 'LOCATION'): BRICK.hasLocation,
  ('EQUIPMENT', 'EQUIPMENT'): BRICK.hasPart,
}

class brickname_parser:
    def __init__(self,
                 grammar_file_name='simple_naming_grammar.ebnf',
                 brick_url = 'https://github.com/BrickSchema/Brick/releases/download/v1.1.0/Brick.ttl'):
        sys.setrecursionlimit(10 ** 5)
        self.parser = self.create_brickname_parser(grammar_file_name, brick_url)
        
    def create_brickname_parser(self, grammar_file_name, brick_url):
        self.brick_entity_list = self.load_brick_ttl(brick_url)

        grammar = ""
        with open(grammar_file_name, "r") as f:
            grammar = f.read()

        new_parser = Lark(grammar)
        return new_parser

    def load_brick_ttl(self, brick_url):
        self.brick_graph = Graph()
        self.brick_graph.parse(brick_url, format='ttl')
        print("loaded brick", brick_url , len(self.brick_graph))

        brick_entity_list = {"Point":[], "Equipment":[], "Location":[]}

        q = """SELECT DISTINCT ?e
        WHERE {{
        ?e rdfs:subClassOf+ brick:{}.
        }}"""
            
        for k, v in brick_entity_list.items():
            qres = self.brick_graph.query(
                q.format(k)
            )
            brick_entity_list[k] = [e[0].split("#")[-1].lower() for e in qres]
            brick_entity_list[k].insert(0, k.lower())

        return brick_entity_list

    def parse(self, input):
        return self.parser.parse(input)

    def lookup_superclass(self, classname):
       if classname.lower() in self.brick_entity_list['Location']:
           return 'LOCATION'
       if classname.lower() in self.brick_entity_list['Point']:
           return 'POINT'
       if classname.lower() in self.brick_entity_list['Equipment']:
           return 'EQUIPMENT'


brick_parser = brickname_parser()

def lookup_rel(left, right, rel, parser):
    localrel = rel.lower()
    if localrel == "[haspart]":
        return BRICK.hasPart
    elif localrel == "[haspoint]":
        return BRICK.hasPoint
    elif localrel == "[islocationof]":
        return BRICK.isLocationOf
    elif localrel == "[feeds]":
        return BRICK.feeds
    elif localrel == ">":
        return BRICK.feeds

    left_super = parser.lookup_superclass(left) 
    right_super = parser.lookup_superclass(right)
    if localrel == "/":
        return rules[(left_super, right_super)]

    # shouldn't get here and should probably just blow up 
    return BRICK.relationship
   
def process_full_name(name, graph, parser):
    # First, find the entities mentioned in this name
    # these will be every other child
    # so just walk down and add them to the graph
    for child in name[0::2]:
        t = child.children[0].value
        v = child.children[2].value
        graph.add((EX[v], RDF.type, BRICK[t]))

    #
    # There are always an odd number of children
    # because its either 
    # entity
    # or entity REL entity [REL entity]...
    #
    # so we'll take every other entry on the child list
    # starting on the 2nd element
    # (which will be the RELATIONSHIP)
    # and figure out what brick relationship connect 
    # the entities on either side of it, based on their
    # classes
    for i, rel in enumerate(name[1::2]):
        i = (i*2) + 1
        #
        # the entites on either side are trees of type entity with children that are tokens
        # so we want a tuple of (type, value) which are the 0th and 2nd children
        #
        left = (name[i-1].children[0].value, name[i-1].children[2].value)
        right = (name[i+1].children[0].value, name[i+1].children[2].value)
        relstr = name[i].value
        brick_rel = lookup_rel(left[0], right[0], relstr, parser) 
        graph.add((EX[left[1]], brick_rel, EX[right[1]]))
    
    # The last thing in this name is the base entity
    # that we want to reuse, so grab that entity's type and value 
    # and return them
    main_entity = name[-1]
    t = main_entity.children[0].value
    v = main_entity.children[2].value
    return (t, v)

def build_tree(line, graph, name_parser):

    x = name_parser.parse(line)
    part1 = x.find_data("part1")
    # there will only ever be one 'part1'
    part1 = [p for p in part1][0]

    main_entity = process_full_name(part1.children, graph, name_parser)
    part2 = x.find_data("part2")
    # There can be multiple part2s so process them all
    for p in part2:
        rel = p.children[0]
        target = process_full_name(p.children[1:], graph, name_parser)
        relstr = rel.value
        brick_rel = lookup_rel(main_entity[0], target[0], relstr, name_parser)
        graph.add((EX[main_entity[1]], brick_rel, EX[target[1]]))


f = open(input_file) 
full_data = f.readlines()

for line in full_data:
    line = line.rstrip()
    print(line)
    build_tree(line, g, brick_parser)

print('\n\n')
print(g.serialize(format="turtle").decode("utf-8"))
