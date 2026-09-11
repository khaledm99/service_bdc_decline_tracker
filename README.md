# service_bdc_decline_tracker
A python script for processing declined services and scheduling them for customer contact

## Roadmap

- CSV Import (DONE)
    - Import and sanitize csv files containing service decline data
    - Evenly split csv data and give the option to import subsets into
      app or output styled html tables for printing
        - PUSHED OUT OF SCOPE
    - Sanitize malformed data and column names (constraint from CRM we're
      getting data from, as it regularly changes the date format and column names
    - bundle decline lines by RO (repair order) number
    - move RO's to lookup queue

- Lookup Queue (DONE)
    - Imported data does not include customer id's or phone numbers. Requires
      manual lookup
    - Present newly imported RO's one-by-one to lookup customer id and phone
      number
    - Add customer id and phone number to RO
    - Add RO to existing customer in app database, or create new customer
    - move RO's to contact queue

- Contact Queue
    - Present customers one-by-one for contact based on decline dates and 
      contact interval
    - Display relevant customer data and list all existing declines that are
      still unhandled, marked by their contact status and due date
    - Get actions from transition engine so user can mark what has been
      done or is tasked to be done for each decline 
    - Refilter into contact queue or send to outcome/followup queue

- Transition Engine
    - Handles transitions for each decline state based on the action the user
      took
    - For example, a decline due for contact can be transitioned to "awaiting
      reply" after selecting "text sent"
    - Uses config file containing legal state transitions

- Frontend
    - Simple html form frontend

- Event logging and data analysis
    - FOR FUTURE CONSIDERATION
