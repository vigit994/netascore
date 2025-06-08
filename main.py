import subprocess
import sys
import platform
import time
import argparse
import xml.etree.ElementTree as ET
import os
import re
import random
 
def print_manual():
    manual = """
Modification Rules Manual
-------------------------
Supported operations (all keywords MUST be in CAPITALS):
 
Unconditional Rules:
  1. Assignment:
       key=value
     (Sets the tag <key> to <value> only if the tag already exists. If the tag does not exist, the rule is skipped.
      Note: '==' is reserved for conditionals.)
  2. Numeric Modification:
       key+=value   or   key-=value
     (Increments or decrements the numeric value of the tag <key> by <value>.
      If the tag does not exist, the rule is skipped.)
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
       IF <cond1> [AND/OR <cond2> ...] THEN <action> [ELSE <alternate_action>]
  - Each condition can be one of:
         tag_key [==, !=, >=, <=, >, <] value
     OR, to check for the absence/presence of a tag:
         NOTEXISTS <tag_key>
         EXISTS <tag_key>
  - The THEN action and optional ELSE action can be any of the operations above (ASSIGN, INCREMENT, DECREMENT, ADD, REMOVE, UPDATE).
  Example:
       IF LANES>1 AND NOTEXISTS HEIGHT THEN ADD HEIGHT=5 ELSE UPDATE LANES TO 2
 
Frequency-based Execution:
  You can append a frequency specifier to any rule to have it applied only a fraction of the times.
  The syntax is:
       FREQ <numerator>/<denom>
  For example:
       UPDATE MAXSPEED TO 50 FREQ 0.5/1
  This means the update will be applied approximately 50% of the times.
 
Notes:
 - All commands must be written in CAPITALS where specified (e.g. IF, THEN, ELSE, ADD, REMOVE, UPDATE, EXISTS, NOTEXISTS, FREQ, AND, OR).
 - Frequency rules work with both unconditional and conditional operations.
"""
    print(manual)
    sys.exit(0)
 

###########################
# Action Expression Parser
###########################

def tokenize_action_expr(expr):
    """
    Tokenize an action expression.
    It splits the expression into tokens: parentheses, the words AND/OR, and atomic action substrings.
    """
    # The regex splits on parentheses and the operators (as whole words).
    tokens = re.split(r'(\(|\)|\bAND\b|\bOR\b)', expr)
    # Filter out tokens that are empty or whitespace.
    tokens = [token.strip() for token in tokens if token.strip() != '']
    return tokens

def parse_action_expr_tokens(tokens, pos, original_line):
    """
    Recursive descent parser for action expressions.
    Grammar:
      action_expr  -> term (OR term)*
      term         -> factor (AND factor)*
      factor       -> atomic_action | '(' action_expr ')'
    Returns a tuple (node, new_pos)
    """
    node, pos = parse_term(tokens, pos, original_line)
    while pos < len(tokens) and tokens[pos] == "OR":
        pos += 1
        right, pos = parse_term(tokens, pos, original_line)
        node = {"op": "OR", "left": node, "right": right}
    return node, pos

def parse_term(tokens, pos, original_line):
    node, pos = parse_factor(tokens, pos, original_line)
    while pos < len(tokens) and tokens[pos] == "AND":
        pos += 1
        right, pos = parse_factor(tokens, pos, original_line)
        node = {"op": "AND", "left": node, "right": right}
    return node, pos

def parse_factor(tokens, pos, original_line):
    if tokens[pos] == "(":
        pos += 1
        node, pos = parse_action_expr_tokens(tokens, pos, original_line)
        if pos >= len(tokens) or tokens[pos] != ")":
            print(f"Error: Missing closing parenthesis in action expression in rule: {original_line}")
            sys.exit(1)
        pos += 1
        return node, pos
    else:
        # Everything that is not an operator or parenthesis is taken as an atomic action string.
        token = tokens[pos]
        pos += 1
        atomic = parse_action(token, original_line)  # Use the existing atomic action parser.
        return {"type": "atomic", "action": atomic}, pos

def parse_action_expression(expr, original_line):
    """
    Parse a compound action expression.
    Returns an abstract syntax tree (AST) representing the expression.
    Exits with an error if the expression is invalid.
    """
    tokens = tokenize_action_expr(expr)
    if not tokens:
        print(f"Error: Empty action expression in rule: {original_line}")
        sys.exit(1)
    ast, pos = parse_action_expr_tokens(tokens, 0, original_line)
    if pos != len(tokens):
        print(f"Error: Invalid or extra tokens in action expression in rule: {original_line}")
        sys.exit(1)
    return ast

###########################
# Atomic Action Parsing & Execution
###########################

def parse_action(action_string, original_line):
    """
    Parse an atomic action string.
    Supported forms:
      - Assignment: key=value (only if the tag exists)
      - Increment: key+=value
      - Decrement: key-=value
      - ADD: ADD <tag_key>=<value>
      - REMOVE: REMOVE <tag_key>
      - UPDATE: UPDATE <tag_key> TO <value>
      - DONOTHING: DONOTHING
    Returns a dict with keys: action_type, key, value (if applicable).
    Exits if the action is invalid.
    """
    if action_string is None:
        print(f"Error: Missing action in rule: {original_line}")
        sys.exit(1)
    action_string = action_string.strip()
    if action_string == "DONOTHING":
        return {'action_type': 'DONOTHING'}
    elif action_string.startswith("ADD "):
        m = re.match(r'^ADD\s+(\S+)\s*=\s*(.+)$', action_string)
        if m:
            key, value = m.groups()
            return {'action_type': 'ADD', 'key': key, 'value': value}
    elif action_string.startswith("REMOVE "):
        m = re.match(r'^REMOVE\s+(\S+)$', action_string)
        if m:
            key = m.group(1)
            return {'action_type': 'REMOVE', 'key': key}
    elif action_string.startswith("UPDATE "):
        m = re.match(r'^UPDATE\s+(\S+)\s+TO\s+(.+)$', action_string)
        if m:
            key, value = m.groups()
            return {'action_type': 'UPDATE', 'key': key, 'value': value}
    else:
        # Assume the form is key=value, key+=value, or key-=value.
        m = re.match(r'^(\S+)\s*(=|\+=|-=)\s*(.+)$', action_string)
        if m:
            key, op, value = m.groups()
            if op == '==':
                print(f"Error: '==' operator is reserved for conditionals. Use '=' for assignment in rule: {original_line}")
                sys.exit(1)
            if op == '=':
                return {'action_type': 'ASSIGN', 'key': key, 'value': value}
            elif op == '+=':
                return {'action_type': 'INCREMENT', 'key': key, 'value': value}
            elif op == '-=':
                return {'action_type': 'DECREMENT', 'key': key, 'value': value}
    print(f"Error: Invalid action in rule: {original_line}")
    sys.exit(1)

def execute_atomic_action(way, action):
    """
    Executes an atomic action on the given way.
    Returns True if the way is modified, False otherwise.
    """
    key = action.get('key')
    action_type = action.get('action_type')
    if action_type == 'ASSIGN':
        tags = way.findall(f"tag[@k='{key}']")
        if tags:
            tags[0].set('v', action.get('value'))
            return True
        return False
    elif action_type in ('INCREMENT', 'DECREMENT'):
        tags = way.findall(f"tag[@k='{key}']")
        if tags:
            try:
                current_value = float(tags[0].get('v'))
                mod_value = float(action.get('value'))
                new_value = current_value + mod_value if action_type == 'INCREMENT' else current_value - mod_value
                tags[0].set('v', str(new_value))
                return True
            except ValueError:
                print(f"Warning: Skipping {action_type} for non-numeric '{key}' in way {way.get('id')}")
                return False
        return False
    elif action_type == 'ADD':
        tags = way.findall(f"tag[@k='{key}']")
        if not tags:
            new_tag = ET.SubElement(way, 'tag')
            new_tag.set('k', key)
            new_tag.set('v', action.get('value'))
            return True
        return False
    elif action_type == 'REMOVE':
        tags = way.findall(f"tag[@k='{key}']")
        if tags:
            for tag in tags:
                way.remove(tag)
            return True
        return False
    elif action_type == 'UPDATE':
        tags = way.findall(f"tag[@k='{key}']")
        if tags:
            tags[0].set('v', action.get('value'))
        else:
            new_tag = ET.SubElement(way, 'tag')
            new_tag.set('k', key)
            new_tag.set('v', action.get('value'))
        return True
    elif action_type == 'DONOTHING':
        return False
    else:
        print(f"Error: Unknown action type: {action_type}")
        sys.exit(1)

def execute_action_ast(way, ast):
    """
    Recursively execute an action expression AST on the given way.
    For an atomic node, execute the atomic action.
    For an AND node, execute both sides sequentially.
    For an OR node, execute the left side and, if it returns False, execute the right side.
    Returns True if the action (or chosen alternative) modifies the way.
    """
    if ast.get("type") == "atomic":
        return execute_atomic_action(way, ast["action"])
    elif "op" in ast:
        op = ast["op"]
        if op == "AND":
            left_res = execute_action_ast(way, ast["left"])
            right_res = execute_action_ast(way, ast["right"])
            return left_res and right_res
        elif op == "OR":
            left_res = execute_action_ast(way, ast["left"])
            if left_res:
                return True
            return execute_action_ast(way, ast["right"])
    else:
        print("Error: Invalid AST node in action expression")
        sys.exit(1)

###########################
# Condition Parsing and Evaluation
###########################

def shunting_yard(tokens):
    """
    Convert a list of tokens (conditions and operators) to Reverse Polish Notation (RPN)
    using a simple shunting yard algorithm. AND has higher precedence than OR.
    """
    output_queue = []
    op_stack = []
    prec = {"AND": 2, "OR": 1}
    for token in tokens:
        if token in ("AND", "OR"):
            while op_stack and op_stack[-1] in ("AND", "OR") and prec[op_stack[-1]] >= prec[token]:
                output_queue.append(op_stack.pop())
            op_stack.append(token)
        else:
            output_queue.append(token)
    while op_stack:
        output_queue.append(op_stack.pop())
    return output_queue

def parse_conditions(conditions_str, original_line):
    """
    Parse an arbitrary condition string that can contain multiple conditions connected by AND/OR.
    Returns the conditions in Reverse Polish Notation (RPN) as a list of tokens.
    Exits if any condition is invalid.
    """
    tokens = re.split(r'\s+(AND|OR)\s+', conditions_str)
    tokens = [token.strip() for token in tokens if token.strip() != '']
    if len(tokens) % 2 == 0:
        print(f"Error: Invalid condition expression in rule: {original_line}")
        sys.exit(1)
    return shunting_yard(tokens)

def evaluate_single_condition(way, condition_str, original_line):
    """
    Evaluate a single condition string against the provided way.
    Supported forms:
      - NOTEXISTS <tag_key>
      - EXISTS <tag_key>
      - <tag_key> [==, !=, >=, <=, >, <] <value>
    Exits if the condition is invalid.
    """
    if condition_str.startswith("NOTEXISTS "):
        tag_key = condition_str[len("NOTEXISTS "):].strip()
        return (len(way.findall(f"tag[@k='{tag_key}']")) == 0)
    if condition_str.startswith("EXISTS "):
        tag_key = condition_str[len("EXISTS "):].strip()
        return (len(way.findall(f"tag[@k='{tag_key}']")) == 1)
    m = re.match(r'^(\S+)\s*(==|!=|>=|<=|>|<)\s*(\S+)$', condition_str)
    if not m:
        print(f"Error: Invalid condition '{condition_str}' in rule: {original_line}")
        sys.exit(1)
    cond_key, cond_op, cond_value = m.groups()
    tags = way.findall(f"tag[@k='{cond_key}']")
    if not tags:
        return False
    tag_val = tags[0].get('v')
    try:
        tag_val_num = float(tag_val)
        cond_val_num = float(cond_value)
        if cond_op == '>':
            return tag_val_num > cond_val_num
        elif cond_op == '<':
            return tag_val_num < cond_val_num
        elif cond_op == '>=':
            return tag_val_num >= cond_val_num
        elif cond_op == '<=':
            return tag_val_num <= cond_val_num
        elif cond_op == '==':
            return tag_val_num == cond_val_num
        elif cond_op == '!=':
            return tag_val_num != cond_val_num
    except ValueError:
        if cond_op == '==':
            return tag_val == cond_value
        elif cond_op == '!=':
            return tag_val != cond_value
        else:
            print(f"Error: Non-numeric comparison for '{cond_key}' in rule: {original_line}")
            sys.exit(1)

def evaluate_rpn(way, rpn_tokens, original_line):
    """
    Evaluate the RPN expression (list of condition tokens and operators) for the given way.
    Returns True or False.
    Exits if the expression is invalid.
    """
    stack = []
    for token in rpn_tokens:
        if token in ("AND", "OR"):
            if len(stack) < 2:
                print(f"Error: Insufficient operands for operator {token} in rule: {original_line}")
                sys.exit(1)
            b = stack.pop()
            a = stack.pop()
            if token == "AND":
                stack.append(a and b)
            else:
                stack.append(a or b)
        else:
            result = evaluate_single_condition(way, token, original_line)
            stack.append(result)
    if len(stack) != 1:
        print(f"Error: Invalid condition expression in rule: {original_line}")
        sys.exit(1)
    return stack[0]

###########################
# Rule Parsing
###########################

def parse_modification_rules(file_path):
    """
    Parse modification rules from a text file.
    Supports both unconditional and conditional rules with extended syntax.
    Exits immediately if any rule is invalid (ignoring lines starting with '#').
    Returns a list of rule dictionaries.
    """
    rules = []
    with open(file_path, 'r') as f:
        for orig_line in f:
            original_line = orig_line.strip().replace("\\xa0", ' ')
            if not original_line or original_line.startswith('#'):
                continue

            # Check for frequency specifier.
            freq = None
            if "FREQ" in original_line:
                parts = original_line.split("FREQ")
                line = parts[0].strip()
                freq_str = parts[1].strip()
                try:
                    numerator, denominator = freq_str.split('/')
                    freq = float(numerator) / float(denominator)
                except Exception as e:
                    print(f"Error: Invalid frequency format in rule: {original_line}")
                    sys.exit(1)
            else:
                line = original_line

            if line.startswith("IF "):
                m = re.match(r'^IF\s+(.+?)\s+THEN\s+(.+?)(?:\s+ELSE\s+(.+))?$', line)
                if not m:
                    print(f"Error: Invalid conditional rule syntax: {original_line}")
                    sys.exit(1)
                conditions_part = m.group(1).strip()
                then_action_part = m.group(2).strip()
                else_action_part = m.group(3).strip() if m.group(3) else None

                conditions_rpn = parse_conditions(conditions_part, original_line)
                then_action_ast = parse_action_expression(then_action_part, original_line)
                else_action_ast = parse_action_expression(else_action_part, original_line) if else_action_part else None
                rule = {
                    'type': 'conditional',
                    'conditions_rpn': conditions_rpn,
                    'then_action_ast': then_action_ast,
                    'else_action_ast': else_action_ast,
                    'original_line': original_line
                }
                if freq is not None:
                    rule['frequency'] = freq
                rules.append(rule)
            else:
                # Unconditional rule: parse the entire line as a compound action expression.
                action_ast = parse_action_expression(line, original_line)
                rule = {
                    'type': 'unconditional',
                    'action_ast': action_ast
                }
                if freq is not None:
                    rule['frequency'] = freq
                rules.append(rule)
    return rules

###########################
# Applying Modifications
###########################

def apply_modifications(root, rules):
    """
    Apply modification rules to all 'way' elements in the OSM XML.
    Supports unconditional and conditional rules with compound action expressions and frequency-based execution.
    """
    for way in root.findall('way'):
        for rule in rules:
            if 'frequency' in rule:
                if random.random() >= rule['frequency']:
                    continue  # Skip this rule for the current way

            if rule['type'] == 'unconditional':
                execute_action_ast(way, rule['action_ast'])
            elif rule['type'] == 'conditional':
                conditions_met = evaluate_rpn(way, rule['conditions_rpn'], rule['original_line'])
                if conditions_met:
                    execute_action_ast(way, rule['then_action_ast'])
                elif rule.get('else_action_ast'):
                    execute_action_ast(way, rule['else_action_ast'])

###########################
# Other Utility Functions
###########################

def modify_file_content(file_path, replacements):
    with open(file_path, 'r') as f:
        content = f.read()
    for key, value in replacements.items():
        content = content.replace(f'${{{key}}}', value)
    return content

def is_docker_running():
    try:
        result = subprocess.run(['docker', 'info'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return result.returncode == 0
    except Exception as e:
        print(f"Error checking Docker status: {e}")
        return False

def start_docker():
    try:
        if platform.system() == "Windows":
            subprocess.run(['start', 'docker'], shell=True)
        elif platform.system() == "Darwin":
            subprocess.run(['open', '-a', 'Docker'])
        elif platform.system() == "Linux":
            subprocess.run(['sudo', 'systemctl', 'start', 'docker'])
        else:
            print("Unsupported platform for starting Docker.")
            sys.exit(1)
        print("Attempting to start Docker. Please wait...")
        time.sleep(10)
    except Exception as e:
        print(f"Failed to start Docker: {e}")
        sys.exit(1)

def clean_docker_environment():
    temp_files = ['data/temp_import.yml', 'data/temp_download.yml']
    for temp_file in temp_files:
        if os.path.exists(temp_file):
            os.remove(temp_file)
    try:
        print("Pruning all Docker containers and images...")
        subprocess.run("docker system prune -a -f", shell=True, check=True)
    except Exception as e:
        print(f"Warning: Failed to prune Docker system: {e}")
    try:
        subprocess.run("docker rmi -f netascore", shell=True, check=True)
    except Exception as e:
        print("Netascore image not found or failed to remove; proceeding.")

###########################
# Main Routine
###########################

def main():
    parser = argparse.ArgumentParser(description="Automate NetAScore scenario generation.")
    parser.add_argument('--city', required=True, help="Name of the city")
    parser.add_argument('--scenario_name', required=False, help="Name of the scenario")
    parser.add_argument('--flag', choices=['ALL', 'CITY', 'SCENARIO'], required=True, help="Action to perform")
    parser.add_argument('--mod_file', help="Path to modification text file", required=False, default="modifications.txt")
    parser.add_argument('--manual', action='store_true', help="Print the modification rules manual and exit")
    args = parser.parse_args()

    if args.manual:
        print_manual()

    city = args.city
    scenario = args.scenario_name
    flag = args.flag
    mod_file = args.mod_file

    if not is_docker_running():
        print("Docker is not running. Attempting to start Docker...")
        start_docker()
        if not is_docker_running():
            print("Failed to start Docker. Please start Docker manually and try again.")
            sys.exit(1)
    else:
        print("Docker is already running.")

    clean_docker_environment()
    print("Docker environment cleaned. Continuing with the script...")

    if flag in ('SCENARIO', 'ALL') and not mod_file:
        parser.error("--mod_file is required when flag is SCENARIO or ALL")

    download_yaml = 'data/settings_osm_query_download.yml'
    import_yaml = 'data/settings_osm_query_import.yml'
    xml_input = f'data/osm_download_{city}.xml'
    xml_output = f'data/osm_download_{city}_{scenario}.xml'

    if flag in ('CITY', 'ALL'):
        download_content = modify_file_content(download_yaml, {'CITY': city})
        temp_download_yaml = 'data/temp_download.yml'
        with open(temp_download_yaml, 'w') as f:
            f.write(download_content)
        print(f"Running Netascore for {city}...")
        subprocess.run(['docker', 'compose', 'run', '--build', 'netascore', temp_download_yaml], check=True)
        if os.path.exists(temp_download_yaml):
            os.remove(temp_download_yaml)

    if flag in ('SCENARIO', 'ALL'):
        if not os.path.exists(xml_input):
            raise FileNotFoundError(f"Input file {xml_input} does not exist. Run with --flag CITY first.")
        rules = parse_modification_rules(mod_file)
        tree = ET.parse(xml_input)
        root = tree.getroot()
        apply_modifications(root, rules)
        tree.write(xml_output)
        import_content = modify_file_content(import_yaml, {'CITY': city, 'SCENARIO': scenario})
        temp_import_yaml = 'data/temp_import.yml'
        with open(temp_import_yaml, 'w') as f:
            f.write(import_content)
        print(f"Running scenario {scenario} for {city}...")
        subprocess.run(['docker', 'compose', 'run', '--build', 'netascore', temp_import_yaml], check=True)
        if os.path.exists(temp_import_yaml):
            os.remove(temp_import_yaml)

if __name__ == '__main__':
    main()
