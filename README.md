# NetAScore - Network Assessment Score Toolbox for Sustainable Mobility

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/plus-mobilitylab/netascore/assets/82904077/762dc210-1ca5-4ead-8aeb-522e974a93fe">
  <source media="(prefers-color-scheme: light)" srcset="https://github.com/plus-mobilitylab/netascore/assets/82904077/240d09f8-a728-41ec-b0e7-8bba8fac4d38">
  <img alt="Shows the NetAScore logo, either with light or dark background depending on the Users settings." src="https://github.com/plus-mobilitylab/netascore/assets/82904077/240d09f8-a728-41ec-b0e7-8bba8fac4d38">
</picture>

## How to use this exention
With this extention, it will be possible to make scenarios using NetAScore. To do so, please donload the whole program from here and not from the main page. 
Step 1: download NetAScore
Step 2: make the scenario (instructions on how to do this follow later)
Step 3: open the Docker environment
Step 4: go on the NetAScore folder and open it
Step 5: right click on a white part of the folder (for example all the way to the right) and open the terminal
Step 6: type the following command python .\main.py --city [...] --flag [...] --scenario_name [...]
In the city add the city's name exactly as found in the OpenStreetMap environment. For "flag" you have three options: CITY will only download the data from OSM as is and not make any scenarios; ALL will download both the base city data and that modified using your rules; SCENARIO will only download the scenarios but note that this only works if there is a base case already dowloaded. In "scenario name" add the name of the scenario that you want and it will be appended to the name of the base scenario. For example: python .\main.py --city London --flag ALL --scenario_name example
Step 7: run the scenario. You will find the output in the folder called data. 

## How to make scenarios
To make scenarios you have to use the file "modifications" which is automatically downloaded. Open it, for example, in the notebook app and write the rules for the change. 
### Syntax available
Unconditional Rules:
  1. Assignment:
       key=value
     (Sets the tag <key> to <value> only if the tag already exists. If the tag does not exist, the rule is skipped.
      Note: '==' is reserved for conditionals.)
  2. Numeric Modification:
       key+=value   or   key-=value
     (Increments or decrements the numeric value of the tag <key> by <value>. If the tag does not exist, the rule is skipped.)
  3. ADD Operation:
       ADD <tag_key>=<value>
     (Adds the tag <tag_key> with the specified <value> only if it does not already exist.)
  4. REMOVE Operation:
       REMOVE <tag_key>
     (Removes the tag <tag_key> from the way if it exists.)
  5. UPDATE Operation:
       UPDATE <tag_key> TO <value>
     (Updates the tag <tag_key> to <value>. If the tag does not exist, it is created.)
  6. DONOTHING Operation:
       DONOTHING
     (Does not perform any action; useful for explicitly having no operation in a conditional ELSE clause.)

 
Conditional Rules:
  Use the following syntax to combine conditions with THEN an action and optionally ELSE an alternate action:
       IF <tag_key> [AND/OR <tag> ...] THEN action [ELSE alternate_action]
  - Each condition can be one of:
         <tag_key> [==, !=, >=, <=, >, <] <value>
     OR, to check for the absence of a tag:
         NOTEXISTS <tag_key>
  - The THEN action and optional ELSE action can be any of the operations above (ASSIGN, INCREMENT, DECREMENT, ADD, REMOVE, UPDATE).
 
Frequency-based Execution:
  You can append a frequency specifier to any rule to have it applied only a fraction of the times.
  The syntax is:
       FREQ <numerator>/<denom>
  For example:
       UPDATE maxspeed TO 50 FREQ 0.5/1
  This means the update will be applied approximately 50% of the times. FREQ is applied to the WHOLE rule, not to specific IF/ELSE conditions
 
Notes:
 - All COMMANDS must be written in CAPITALS where specified (e.g. IF, THEN, ELSE, ADD, REMOVE, UPDATE, NOTEXISTS, FREQ, AND, OR).
 - Frequency rules work with both unconditional and conditional operations.

### What can be done
This syntax only acts on links. Therefore, it is possible to update values, add tags and their values, specifify how often this should happen (the specific links are chosen at random), remove tags etc.   Example: IF lanes>1 AND NOTEXISTS maxspeed THEN ADD maxspeed=50 ELSE UPDATE lanes TO 2.
**remember to always use the names that OSM uses to name tags and their values**

## Notes
In this version of NetAScore the attribute for street parking is calculated and has been given a mapping. Still, if your city does not have rich data about parking, it will not play much of a role. 
