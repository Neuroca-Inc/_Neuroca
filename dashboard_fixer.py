import yaml
import json
import sys

def fix_grafana_dashboard_ids(yaml_content_string):
    """
    Parses YAML, finds the Grafana dashboard JSON, checks and corrects duplicate/invalid panel IDs.

    Args:
        yaml_content_string: A string containing the YAML content.

    Returns:
        A tuple: (new_yaml_content_string_or_none, report_message)
                 If changes were made, the first element is the updated YAML string.
                 If no changes or an error occurs, the first element is None.
                 The second element is a message describing what happened.
    """
    try:
        yaml_docs = list(yaml.safe_load_all(yaml_content_string))
    except yaml.YAMLError as e:
        return None, f"Error parsing YAML: {e}"

    grafana_cm = None
    doc_index_cm = -1
    for i, doc in enumerate(yaml_docs):
        if doc and doc.get('kind') == 'ConfigMap' and doc.get('metadata', {}).get('name') == 'grafana-dashboards':
            grafana_cm = doc
            doc_index_cm = i
            break

    if not grafana_cm:
        return None, "ConfigMap 'grafana-dashboards' not found."

    dashboard_json_str = grafana_cm.get('data', {}).get('neuroca-overview.json')
    if not dashboard_json_str:
        return None, "'neuroca-overview.json' not found in ConfigMap 'grafana-dashboards'."

    try:
        dashboard_data = json.loads(dashboard_json_str)
    except json.JSONDecodeError as e:
        return None, f"Error parsing 'neuroca-overview.json': {e}"

    main_dashboard_id = dashboard_data.get('id')
    panel_ids_seen = set()
    if main_dashboard_id is not None and isinstance(main_dashboard_id, int):
        # According to the problem, the main dashboard ID should not be reused by panels.
        # However, the logic focuses on panel ID uniqueness among themselves and being integers.
        # For now, we won't add main_dashboard_id to panel_ids_seen unless requirements change.
        pass

    changes_made = False
    panels = dashboard_data.get('panels', [])
    new_panels = []
    next_panel_id_counter = 100 # Start high to avoid clashes

    if not isinstance(panels, list):
        return None, f"'panels' field is not a list in 'neuroca-overview.json'."

    for panel in panels:
        if not isinstance(panel, dict):
            new_panels.append(panel) # Keep non-dict items as is
            continue

        current_panel_id = panel.get('id')
        is_problematic = False

        if current_panel_id is None or not isinstance(current_panel_id, int):
            is_problematic = True
        elif current_panel_id in panel_ids_seen:
            is_problematic = True

        # Also ensure panel ID does not clash with the main dashboard ID if it's an integer
        if main_dashboard_id is not None and isinstance(main_dashboard_id, int) and current_panel_id == main_dashboard_id:
            is_problematic = True


        if is_problematic:
            while next_panel_id_counter in panel_ids_seen or next_panel_id_counter == main_dashboard_id:
                next_panel_id_counter += 1
            panel['id'] = next_panel_id_counter
            panel_ids_seen.add(next_panel_id_counter)
            next_panel_id_counter += 1
            changes_made = True
        else:
            panel_ids_seen.add(current_panel_id)

        new_panels.append(panel)

    if changes_made:
        dashboard_data['panels'] = new_panels
        # Pretty print JSON with an indent of 2 spaces, matching the original format
        # Also ensure keys are not sorted to maintain original order as much as possible
        new_dashboard_json_str = json.dumps(dashboard_data, indent=2, sort_keys=False)

        # Update the ConfigMap in the YAML structure
        yaml_docs[doc_index_cm]['data']['neuroca-overview.json'] = new_dashboard_json_str

        # Serialize the YAML documents back to a string
        # Ensure the multi-line JSON string is preserved correctly using a literal block scalar style
        class MyDumper(yaml.SafeDumper):
            def represent_scalar(self, tag, value, style=None):
                if '\n' in value: # Check if multiline
                    return self.represent_scalar(tag, value, style='|')
                return super().represent_scalar(tag, value, style)

        updated_yaml_content = yaml.dump_all(yaml_docs, Dumper=MyDumper, sort_keys=False, default_flow_style=False, width=float("inf"))
        return updated_yaml_content, "Panel IDs were renumbered due to duplicates or invalid types."
    else:
        return None, "No changes to panel IDs were necessary. All panel IDs are unique integers and valid."

if __name__ == "__main__":
    # Read from stdin or a file
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
        try:
            with open(filepath, 'r') as f:
                content = f.read()
        except FileNotFoundError:
            print(f"Error: File not found {filepath}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error reading file {filepath}: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        content = sys.stdin.read()

    if not content:
        print("Error: No YAML content provided to script.", file=sys.stderr)
        sys.exit(1)

    new_yaml, message = fix_grafana_dashboard_ids(content)

    print(message, file=sys.stderr) # Report message to stderr
    if new_yaml:
        print(new_yaml) # New YAML to stdout
        sys.exit(0) # Exit code 0 if changes were made and successful
    else:
        # If no changes, or error, exit with appropriate code
        if "Error" in message or "not found" in message:
             sys.exit(1) # Error
        else:
             sys.exit(2) # No changes needed
