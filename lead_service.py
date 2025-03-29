import re

class ValidationException(Exception):
    def __init__(self, messages):
        self.messages = messages
        super().__init__(str(messages))


class LeadService:
    def __init__(self, lead_repo, sales_agent_repo, notification_service):
        self.lead_repo = lead_repo
        self.sales_agent_repo = sales_agent_repo
        self.notification_service = notification_service

    def process_lead(self, lead_data: dict):
        # 1. Check if lead has email or phone number
        if not lead_data.get('email') and not lead_data.get('phone'):
            raise ValidationException({'error': 'Lead must have email or phone number'})

        if not self.is_valid_email(lead_data.get('email')) or not self.is_valid_phone(lead_data.get('phone')):
            raise ValidationException({'error': 'Invalid email or phone format'})

        # 2. Check if lead already exists
        lead = self.lead_repo.find_by_email_or_phone(lead_data.get('email'), lead_data.get('phone'))

        if lead:
            # 3. If lead exists, update lead data
            self.lead_repo.update(lead['id'], lead_data)
            return {'message': 'Lead updated'}

        # 4. Determine region from location
        if lead_data.get('location'):
            lead_data['region'] = self.determine_region(lead_data['location'])

        # 5. Assign lead to sales agent
        sales_agent = self.sales_agent_repo.get_best_available_agent()

        if not sales_agent:
            # 6. If no available sales agent, add lead to waiting queue
            self.lead_repo.save_to_waiting_queue(lead_data)
            return {'message': 'No available sales agents. Lead added to waiting queue.'}

        # 7. Create new lead and assign to sales agent
        lead_data['assigned_agent'] = sales_agent['id']
        new_lead = self.lead_repo.create(lead_data)

        # 8. Send notification to sales agent
        self.notification_service.send(sales_agent['id'], f"New lead assigned: {new_lead['name']}")

        # 9. Log lead process
        self.lead_repo.log_lead_process(new_lead['id'], sales_agent['id'], 'Lead assigned successfully')

        return {'message': 'New lead created and assigned', 'assigned_to': sales_agent['name']}
    
    @staticmethod
    def is_valid_email(email):
        if not email:
            return False
        
        regex = r'^[^@]+@[^@]+\.[^@]+$'
        return re.match(regex, email) is not None

    @staticmethod
    def is_valid_phone(phone):
        if not phone:
            return False
        
        return re.match(r'^\+?[0-9]{7,15}$', phone) is not None

    @staticmethod
    def determine_region(location):
        # Determine region from location
        return 'default-region'