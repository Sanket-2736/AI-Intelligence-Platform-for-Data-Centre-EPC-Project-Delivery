# Sample Data for EPC Intelligence Platform

This directory contains sample data files used for testing and demonstration of the EPC Intelligence Platform.

## Files

### Generated Data Files
- `schedule_001.xlsx` - Sample project schedule (120 tasks, data centre construction)
- `schedule_002.xlsx` - Alternative schedule with different phases
- `schedule_003.xlsx` - Complex schedule with dependencies
- `shipments.csv` - Sample shipment data with 20 equipment items

### PDF Reference Files
These are sourced from public domain or Creative Commons licensed documents:
- `sample_specification.pdf` - Example equipment specification (public domain)
- `sample_manual.pdf` - Example technical manual (public domain)

## Generating Sample Data

Run the sample data generator to create realistic test data:

```bash
python generate_samples.py
```

This will create:
1. Three Excel schedules with realistic EPC project tasks
2. A CSV file with shipment data including coordinates for mapping
3. Sample PDFs (if available) for testing document ingestion

## Data Structure

### Schedule Files (Excel)
- Task ID
- Task Name
- Predecessor Tasks
- Duration (days)
- Resource Requirements
- Status
- Risk Level
- Assigned To

### Shipments (CSV)
- Equipment Name
- Supplier
- Origin Country
- Current Location
- ETA
- Required on Site
- Status
- Latitude
- Longitude

## Notes

- All sample data is fictional and for testing purposes only
- Coordinates use real locations (port cities, data centres) for realistic mapping
- Schedule dates are relative and can be updated for current testing
