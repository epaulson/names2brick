# name2brick
A naming convention that encodes a Brick model in a human-readable but easy-to-parse format, and a tool to do the parsing.

## Usage:
```
python names2brick.py --namespace ex http://example.com/building# names.txt
```

## Description:
This tool converts a set of names into a [Brick Schema](https://brickschema.org) model of a building. 

## Naming Convention
The naming convention this tool expects is designed to provide a general way to encode, in a single string, an entity of the built environment (Space, Equipment, Point, etc) and the relationships of that entity. 

The convention is designed so that the names can be used as common names across multiple data sources, for example, a BACnet point name or a BIM Object name. With a common name, it becomes possible to "join" data from different systems automatically.

Let's start with some examples. First, consider this identifier:

```Building:EBU3B/Chilled_Water_System:3B/Pump:P4/VFD:VFD4/Electrical_Meter:EM4```

In Brick (and how this tool parses this string) we get

```
@prefix brick: <https://brickschema.org/schema/1.1/Brick#> .
@prefix ex: <https://example.com/building/#> .

ex:EBU3B a brick:Building ;
    brick:isLocationOf ex:3B .

ex:3B a brick:Chilled_Water_System ;
    brick:hasPart ex:P4 .

ex:P4 a brick:Pump ;
    brick:hasPart ex:VFD4 .

ex:VFD4 a brick:VFD ;
    brick:hasPart ex:EM4 .

ex:EM4 a brick:Electrical_Meter .
```

The name is built out of multiple segments such as 'Building:EBU3B' and 'Chilled_Water_System:3B'. Each of these segments is a type and an identifier, separated by a ':'. The type is assumed to come from the Brick ontology. For now, the identifier should be unique, e.g. "Pump:4" and "VFD:4" should not both use '4' as their identifier.  

Each segment is connected via a '/' character. That is shorthand for a relationship. The tool uses the [Brick Relationships Guide](https://brickschema.org/relationships) to determine which type of relationship the '/' character should represent, depending on the type of the entities on either side of the '/'. 

The '/' is shorthand for a more general form of identifying a relationship. Our example could have been written as 

```Building:EBU3B[isLocationOf]Chilled_Water_System:3B[hasPart]Pump:P4[hasPart]VFD:VFD4[hasPart]Electrical_Meter:EM4```

Similarly, '>' is shorthand for the feeds relationship

```AHU:AHU1>VAV:VAV1```

translates to

```
@prefix brick: <https://brickschema.org/schema/1.1/Brick#> .
@prefix ex: <https://example.com/building/#> .

ex:AHU1 a brick:AHU ;
    brick:feeds ex:VAV1 .

ex:VAV1 a brick:VAV .
```

### Fully Qualified Name
Consider this example:

```Building:EBU3D/floor:2/Room:203/AHU:SB-AHU2```

In this example, the entity named is ```AHU:SB-AHU2```. The additional entities listed make up the 'fully qualified names' and are expanded into the full graph, but in some instances where we want to identify a single entity, the last entity is used. 

This is useful for being able to attach additional relationships onto an identifier. For example, this name

```Building:EBU3D/floor:2/Room:203/AHU:SB-AHU2,>Room:203/VAV:230A```

translates to this Brick model:
```
@prefix brick: <https://brickschema.org/schema/1.1/Brick#> .
@prefix ex: <https://example.com/building/#> .

ex:EBU3D a brick:Building ;
    brick:hasPart ex:2 .

ex:2 a brick:floor ;
    brick:hasPart ex:203 .

ex:203 a brick:Room ;
    brick:isLocationOf ex:230A,
        ex:SB-AHU2 .

ex:SB-AHU2 a brick:AHU ;
    brick:feeds ex:230A .

ex:230A a brick:VAV .

```
e.g. SB-AHU2 feeds VAV 230A. It is not the case that Building EBU3D feeds VAV 230A, nor does SB-AHU2 feed Room 203. 

It is permitted to put multiple additional relationships onto an identifier, this is permitted and adds two 'feeds' relationships from SB-AHU2 too VAVs 230A and 28BC:

```Building:EBU3D/floor:2/Room:203/AHU:SB-AHU2,>Room:203/VAV:230A,>VAV:28BC```

## Part1 and Part2
In the naming convention, the first set of identifiers, e.g.
```Building:EBU3D/floor:2/Room:203/AHU:SB-AHU2```
is called **part1** of the name and the additional relationships, e.g.
```>Room:203/VAV:230A``` and ```>VAV:28BC``` are both **part2** strings. There can be only a single **part1** component but there can be multiple **part2** components on a given name.


## Reserved Characters
The naming convention reserves certain characters for its own use. These characters are not permitted to appear in 'identifier' portion of the names:

* '['
* ']'
* '/'
* '>'
* '<'
* ':'
* ','

## Formal Grammar
This tool uses the [Lark Parser](https://github.com/lark-parser/lark), which describes its grammar using an EBNF notation. That might be a bit overkill but it gives us some flexibility

```EBNF
start : brick_name
brick_name : part1 (PSEP part2)*
REL: "[hasPoint]"i | "[hasPart]"i | "[isLocationOf]"i | "[feeds]"i | "/" | ">"
part1 : entity (REL entity)*
entity: TYPE CSEP ID
part2: REL entity (REL entity)*

CSEP: ":"
PSEP: ","

TYPE: (LETTER|"_")+
ID: (LETTER|DIGIT|"-"|"_")+
%import common.DIGIT
%import common.LETTER
%import common.WS
%ignore WS
```

## TODO
* Properly validate and normalize Brick classes used in identifiers.
* Cache the Brick TTL download or provide an option to find it locally
* Support output to a file
* Full test suite
* Refactor code to eliminate wonky half OOP/half procedural mess
* Refactor code to use Lark transformers for parsing instead of walking children nodes directly
* Support all Brick relationships
* Validate permitted character classes for identifiers to support both BACnet and BIM
* Add a BACpypes simulator to publish names to validate flow
