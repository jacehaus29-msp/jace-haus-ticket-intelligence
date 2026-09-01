ROUTING_RULES = [
    {
        "name": "Microsoft 365",
        "team": "M365 Support",
        "priority": "high",
        "keywords": [
            "microsoft 365",
            "office 365",
            "outlook",
            "teams",
            "sharepoint",
            "onedrive",
        ],
        "description": "Routes Microsoft 365 and related productivity issues."
    },
    {
        "name": "Network",
        "team": "Network Team",
        "priority": "medium",
        "keywords": [
            "network",
            "wifi",
            "internet",
            "router",
            "switch",
            "vpn",
        ],
        "description": "Routes network connectivity and infrastructure issues."
    },
    {
        "name": "Security",
        "team": "Security Team",
        "priority": "critical",
        "keywords": [
            "phishing",
            "malware",
            "ransomware",
            "suspicious login",
            "security",
        ],
        "description": "Routes security-related incidents and threats."
    },
    {
        "name": "Hardware",
        "team": "Endpoint Team",
        "priority": "medium",
        "keywords": [
            "laptop",
            "desktop",
            "monitor",
            "keyboard",
            "mouse",
            "printer",
        ],
        "description": "Routes hardware and endpoint issues."
    },
    {
        "name": "Backup",
        "team": "Backup Team",
        "priority": "high",
        "keywords": [
            "backup",
            "restore",
            "recovery",
        ],
        "description": "Routes backup, restore and recovery issues."
    },
]
def get_routing_rule(rule_name: str):
    for rule in ROUTING_RULES:
        if rule["name"].lower() == rule_name.lower():
            return rule

    return None