# workout_parser.py
import re
from typing import List, Dict

class WorkoutParser:
    def __init__(self):
        self.sections = []
        self.intervals = []
    
    def parse_chatgpt_workout(self, text: str) -> List[Dict]:
        """
        Parse ChatGPT's workout format into intervals
        """
        if not text or not isinstance(text, str):
            return []
            
        intervals = []
        current_section = None
        repeat_count = 0
        repeat_intervals = []
        in_repeat_block = False
        
        lines = text.split('\n')
        
        for line in lines:
            # Skip empty lines
            if not line.strip():
                continue
            
            # Check for section headers: **Warm-Up – 5 minutes**
            section_pattern = r'\*\*(.+?)\s*–\s*(\d+)\s*minutes?\*\*'
            section_match = re.search(section_pattern, line)
            
            if section_match:
                current_section = section_match.group(1).strip()
                continue
            
            # Check for repeat instruction
            repeat_pattern = r'Repeat.*?(\d+)\s*times'
            repeat_match = re.search(repeat_pattern, line, re.IGNORECASE)
            
            if repeat_match:
                repeat_count = int(repeat_match.group(1))
                in_repeat_block = True
                repeat_intervals = []
                continue
            
            # Parse interval lines: * 5 min @ 5.5 mph (description)
            # Make description optional
            interval_pattern = r'\*?\s*(\d+)\s*min\s*@\s*([\d.]+)\s*mph(?:\s*\((.*?)\))?'
            interval_match = re.search(interval_pattern, line)
            
            if interval_match:
                try:
                    duration = int(interval_match.group(1))
                    speed = float(interval_match.group(2))
                    
                    # Validate inputs
                    if duration <= 0 or speed <= 0:
                        continue  # Skip invalid intervals
                except (ValueError, TypeError):
                    continue  # Skip intervals with invalid numbers
                
                interval = {
                    'section': current_section,
                    'duration_min': duration,
                    'speed_mph': speed,
                    'description': interval_match.group(3) or '',
                    'incline': 0  # We'll add incline parsing later
                }
                
                if in_repeat_block:
                    repeat_intervals.append(interval)
                else:
                    intervals.append(interval)
            
            # Check if we've ended a repeat block
            # (empty line or new section after repeat_intervals)
            if in_repeat_block and repeat_intervals and (
                not line.strip() or section_match
            ):
                # Add repeated intervals
                for _ in range(repeat_count):
                    intervals.extend(repeat_intervals.copy())
                in_repeat_block = False
                repeat_intervals = []
        
        # Handle case where repeat block goes to end of file
        if in_repeat_block and repeat_intervals:
            for _ in range(repeat_count):
                intervals.extend(repeat_intervals.copy())
        
        return intervals

# Module-level function for backwards compatibility
def parse(text):
    return WorkoutParser().parse_chatgpt_workout(text)