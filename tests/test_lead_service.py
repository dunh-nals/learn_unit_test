# File: tests/test_lead_service.py
import pytest
from unittest.mock import Mock
from lead_service import LeadService, ValidationException

# Fixture to create a reusable LeadService instance with mocked dependencies
@pytest.fixture
def lead_service():
    lead_repo = Mock()
    sales_agent_repo = Mock()
    notification_service = Mock()
    return LeadService(lead_repo, sales_agent_repo, notification_service)

# Fixture for valid lead data (includes both email and phone to pass validation)
@pytest.fixture
def valid_lead_data():
    return {
        "email": "test@example.com",
        "phone": "12345678",  # Valid phone number (7-15 digits)
        "name": "John",
    }

# Fixture for valid lead data without location (to test flows where determine_region is not called)
@pytest.fixture
def valid_lead_data_no_location():
    return {
        "email": "test@example.com",
        "phone": "12345678",
        "name": "John",
    }

# Fixture for lead data with only email (to test validation failure)
@pytest.fixture
def lead_data_with_email_only():
    return {
        "email": "test@example.com",
        "name": "John",
    }

# Fixture for lead data with only phone (to test validation failure)
@pytest.fixture
def lead_data_with_phone_only():
    return {
        "phone": "12345678",
        "name": "John",
    }

# Fixture for lead data without email and phone (to test validation failure)
@pytest.fixture
def lead_data_no_contact():
    return {
        "name": "John",
    }

# Group test cases by functionality: Validation-related tests
class TestLeadValidation:
    # Test case: Lead data must have either email or phone, otherwise raise ValidationException
    def test_no_email_or_phone(self, lead_service, lead_data_no_contact):
        with pytest.raises(ValidationException) as exc:
            lead_service.process_lead(lead_data_no_contact)
        assert exc.value.messages["error"] == "Lead must have email or phone number"

    # Test case: Invalid email format should raise ValidationException
    def test_invalid_email_format(self, lead_service):
        lead_data = {
            "email": "invalid-email",  # Invalid email format
            "phone": "12345678",  # Valid phone
            "name": "John",
        }
        with pytest.raises(ValidationException) as exc:
            lead_service.process_lead(lead_data)
        assert exc.value.messages["error"] == "Invalid email or phone format"

    # Test case: Invalid phone format should raise ValidationException
    def test_invalid_phone_format(self, lead_service):
        lead_data = {
            "email": "test@example.com",  # Valid email
            "phone": "123",  # Invalid phone (less than 7 digits)
            "name": "John",
        }
        with pytest.raises(ValidationException) as exc:
            lead_service.process_lead(lead_data)
        assert exc.value.messages["error"] == "Invalid email or phone format"

    # Test case: Lead with only email should fail due to current logic requiring both email and phone
    def test_lead_with_email_only(self, lead_service, lead_data_with_email_only):
        with pytest.raises(ValidationException) as exc:
            lead_service.process_lead(lead_data_with_email_only)
        assert exc.value.messages["error"] == "Invalid email or phone format"

    # Test case: Lead with only phone should fail due to current logic requiring both email and phone
    def test_lead_with_phone_only(self, lead_service, lead_data_with_phone_only):
        with pytest.raises(ValidationException) as exc:
            lead_service.process_lead(lead_data_with_phone_only)
        assert exc.value.messages["error"] == "Invalid email or phone format"

# Group test cases by functionality: Lead processing-related tests
class TestLeadProcessing:
    # Test case: Update an existing lead when location is provided (but determine_region is not called in this flow)
    def test_update_existing_lead_with_location(self, lead_service, valid_lead_data):
        valid_lead_data["location"] = "US"  # Include location
        lead_service.lead_repo.find_by_email_or_phone.return_value = {"id": 1, "name": "John"}
        result = lead_service.process_lead(valid_lead_data)
        lead_service.lead_repo.update.assert_called_once_with(1, valid_lead_data)
        assert result == {"message": "Lead updated"}

    # Test case: Update an existing lead when location is not provided
    def test_update_existing_lead_no_location(self, lead_service, valid_lead_data_no_location):
        lead_service.lead_repo.find_by_email_or_phone.return_value = {"id": 1, "name": "John"}
        result = lead_service.process_lead(valid_lead_data_no_location)
        lead_service.lead_repo.update.assert_called_once_with(1, valid_lead_data_no_location)
        assert result == {"message": "Lead updated"}
        assert "region" not in valid_lead_data_no_location  # No region since determine_region is not called

    # Test case: Add lead to waiting queue when no agent is available, with location
    def test_no_available_agent_with_location(self, lead_service, valid_lead_data):
        valid_lead_data["location"] = "US"  # Include location
        lead_service.lead_repo.find_by_email_or_phone.return_value = None
        lead_service.sales_agent_repo.get_best_available_agent.return_value = None
        result = lead_service.process_lead(valid_lead_data)
        lead_service.lead_repo.save_to_waiting_queue.assert_called_once_with(valid_lead_data)
        assert result == {"message": "No available sales agents. Lead added to waiting queue."}
        assert valid_lead_data["region"] == "default-region"  # Check that determine_region was called

    # Test case: Add lead to waiting queue when no agent is available, without location
    def test_no_available_agent_no_location(self, lead_service, valid_lead_data_no_location):
        lead_service.lead_repo.find_by_email_or_phone.return_value = None
        lead_service.sales_agent_repo.get_best_available_agent.return_value = None
        result = lead_service.process_lead(valid_lead_data_no_location)
        lead_service.lead_repo.save_to_waiting_queue.assert_called_once_with(valid_lead_data_no_location)
        assert result == {"message": "No available sales agents. Lead added to waiting queue."}
        assert "region" not in valid_lead_data_no_location  # No region since determine_region is not called

    # Test case: Create and assign a new lead successfully, with location
    def test_create_and_assign_success_with_location(self, lead_service, valid_lead_data):
        valid_lead_data["location"] = "US"  # Include location
        lead_service.lead_repo.find_by_email_or_phone.return_value = None
        lead_service.sales_agent_repo.get_best_available_agent.return_value = {"id": 1, "name": "Agent1"}
        lead_service.lead_repo.create.return_value = {"id": 2, "name": "John"}
        result = lead_service.process_lead(valid_lead_data)
        lead_service.lead_repo.create.assert_called_once()
        lead_service.notification_service.send.assert_called_once_with(1, "New lead assigned: John")
        lead_service.lead_repo.log_lead_process.assert_called_once_with(2, 1, "Lead assigned successfully")
        assert result == {"message": "New lead created and assigned", "assigned_to": "Agent1"}
        assert valid_lead_data["region"] == "default-region"  # Check that determine_region was called

    # Test case: Create and assign a new lead successfully, without location
    def test_create_and_assign_success_no_location(self, lead_service, valid_lead_data_no_location):
        lead_service.lead_repo.find_by_email_or_phone.return_value = None
        lead_service.sales_agent_repo.get_best_available_agent.return_value = {"id": 1, "name": "Agent1"}
        lead_service.lead_repo.create.return_value = {"id": 2, "name": "John"}
        result = lead_service.process_lead(valid_lead_data_no_location)
        lead_service.lead_repo.create.assert_called_once()
        lead_service.notification_service.send.assert_called_once_with(1, "New lead assigned: John")
        lead_service.lead_repo.log_lead_process.assert_called_once_with(2, 1, "Lead assigned successfully")
        assert result == {"message": "New lead created and assigned", "assigned_to": "Agent1"}
        assert "region" not in valid_lead_data_no_location  # No region since determine_region is not called

# Group test cases by functionality: Utility method tests
class TestUtilityMethods:
    # Test case: Validate the is_valid_email method with various inputs
    def test_is_valid_email(self):
        assert LeadService.is_valid_email("test@example.com") is True
        assert LeadService.is_valid_email("invalid") is False
        assert LeadService.is_valid_email("") is False
        assert LeadService.is_valid_email(None) is False
        assert LeadService.is_valid_email("test@.com") is False

    # Test case: Validate the is_valid_phone method with various inputs
    def test_is_valid_phone(self):
        assert LeadService.is_valid_phone("+1234567890") is True
        assert LeadService.is_valid_phone("12345678") is True
        assert LeadService.is_valid_phone("123") is False
        assert LeadService.is_valid_phone("") is False
        assert LeadService.is_valid_phone(None) is False
        assert LeadService.is_valid_phone("abc1234567") is False

    # Test case: Validate the determine_region method with various inputs
    def test_determine_region(self):
        assert LeadService.determine_region("US") == "default-region"
        assert LeadService.determine_region(None) == "default-region"
        assert LeadService.determine_region("") == "default-region"