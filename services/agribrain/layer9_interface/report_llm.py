"""
Layer 9.3: Report Generator.
Generates Multi-Format Reports (Farmer, Agronomist, Govt).
"""

from typing import Dict, Any, List

class ReportGenerator:
    
    def generate_report(self, context: Dict[str, Any], report_type: str = "farmer") -> str:
        """
        Generate Markdown report.
        """
        plot = context.get("plot", {})
        yield_data = context.get("yield", {})
        actions = context.get("top_actions", [])
        
        lines = []
        lines.append(f"# AgriBrian {report_type.capitalize()} Report")
        lines.append(f"**Plot**: {plot.get('crop', 'Crop')} ({plot.get('id', 'Unknown')})")
        lines.append(f"**Date**: 2023-XX-XX\n")
        
        if report_type == "farmer":
            # Concise, Action-Oriented
            lines.append("## 🚜 Top Actions")
            for act in actions[:3]:
                lines.append(f"- **{act['action']}**: Gain ${act['profit_gain']:.0f}")
                
            lines.append("\n## 📉 Outlook")
            lines.append(f"Expected Yield: {yield_data.get('mean')} t/ha")
            
        elif report_type == "agronomist":
            # Detailed, Evidence-Based
            lines.append("## 🔬 Technical Analysis")
            lines.append(f"Yield P10-P90: {yield_data.get('p10')} - {yield_data.get('p90')} t/ha")
            lines.append("### Attribution")
            attr = yield_data.get("attribution", {})
            for k, v in attr.items():
                lines.append(f"- {k}: {v:.2f} impact")
                
            lines.append("\n## 📋 Recommendations")
            for act in actions:
                lines.append(f"1. **{act['action']}**: {act['reason']} (Conf: {act['confidence']})")
                
        return "\n".join(lines)

# Singleton
reporter = ReportGenerator()
