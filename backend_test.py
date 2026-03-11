import requests
import sys
import json
from datetime import datetime

class LightlineAPITester:
    def __init__(self, base_url="https://outline-hub-1.preview.emergentagent.com/api"):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.results = []

    def log_result(self, test_name, passed, details=""):
        """Log test result"""
        self.tests_run += 1
        if passed:
            self.tests_passed += 1
        
        result = {
            "test": test_name,
            "status": "PASS" if passed else "FAIL",
            "details": details
        }
        self.results.append(result)
        
        status_icon = "✅" if passed else "❌"
        print(f"{status_icon} {test_name}: {'PASS' if passed else 'FAIL'}")
        if details and not passed:
            print(f"   Details: {details}")

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        request_headers = {'Content-Type': 'application/json'}
        if self.token:
            request_headers['Authorization'] = f'Bearer {self.token}'
        if headers:
            request_headers.update(headers)

        try:
            if method == 'GET':
                response = requests.get(url, headers=request_headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=request_headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=request_headers, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, headers=request_headers, timeout=10)

            success = response.status_code == expected_status
            details = f"Status: {response.status_code}, Expected: {expected_status}"
            if not success:
                details += f", Response: {response.text[:200]}"
            
            self.log_result(name, success, details)
            return success, response.json() if success and response.text else {}

        except Exception as e:
            self.log_result(name, False, f"Error: {str(e)}")
            return False, {}

    def test_root_endpoint(self):
        """Test root API endpoint"""
        return self.run_test("Root API", "GET", "", 200)

    def test_login(self):
        """Test admin login with default credentials"""
        success, response = self.run_test(
            "Admin Login",
            "POST",
            "auth/login",
            200,
            data={"username": "admin", "password": "admin123"}
        )
        if success and 'access_token' in response:
            self.token = response['access_token']
            self.log_result("Token Extraction", True, "Access token obtained")
            return True
        else:
            self.log_result("Token Extraction", False, "Failed to get access token")
            return False

    def test_auth_me(self):
        """Test get current admin info"""
        return self.run_test("Get Current Admin", "GET", "auth/me", 200)

    def test_dashboard(self):
        """Test dashboard endpoint - should return stats"""
        success, response = self.run_test("Dashboard Stats", "GET", "dashboard", 200)
        if success:
            # Verify expected dashboard fields
            required_fields = ['nodes', 'users', 'traffic', 'license', 'recent_activity', 'node_health']
            missing_fields = [field for field in required_fields if field not in response]
            if missing_fields:
                self.log_result("Dashboard Fields", False, f"Missing fields: {missing_fields}")
                return False
            else:
                self.log_result("Dashboard Fields", True, "All required fields present")
                return True
        return success

    def test_nodes_crud(self):
        """Test nodes CRUD operations"""
        # Test GET nodes - should have 5 mock nodes
        success, nodes = self.run_test("Get Nodes", "GET", "nodes", 200)
        if not success:
            return False

        initial_count = len(nodes)
        if initial_count != 5:
            self.log_result("Initial Nodes Count", False, f"Expected 5 nodes, got {initial_count}")
        else:
            self.log_result("Initial Nodes Count", True, f"Found {initial_count} mock nodes")

        # Test CREATE node
        new_node = {
            "name": "Test Node",
            "ip": "1.2.3.4", 
            "api_port": 12345,
            "api_key": "test_api_key_12345",
            "country": "TEST"
        }
        create_success, create_response = self.run_test("Create Node", "POST", "nodes", 200, new_node)
        if not create_success:
            return False

        node_id = create_response.get('id')
        if not node_id:
            self.log_result("Node ID Extraction", False, "No node ID returned")
            return False

        # Test UPDATE node
        update_data = {"name": "Updated Test Node"}
        update_success, _ = self.run_test(
            "Update Node", 
            "PUT", 
            f"nodes/{node_id}", 
            200, 
            update_data
        )

        # Test health check
        health_success, _ = self.run_test(
            "Node Health Check",
            "POST",
            f"nodes/{node_id}/health-check",
            200
        )

        # Test DELETE node
        delete_success, _ = self.run_test("Delete Node", "DELETE", f"nodes/{node_id}", 200)

        return create_success and update_success and delete_success

    def test_users_crud(self):
        """Test users CRUD operations"""
        # Test GET users - should have 10 mock users
        success, users = self.run_test("Get Users", "GET", "users", 200)
        if not success:
            return False

        initial_count = len(users)
        if initial_count != 10:
            self.log_result("Initial Users Count", False, f"Expected 10 users, got {initial_count}")
        else:
            self.log_result("Initial Users Count", True, f"Found {initial_count} mock users")

        # Test CREATE user
        new_user = {
            "username": "testuser123",
            "password": "testpass123",
            "traffic_limit": 5000000000,  # 5GB
            "device_limit": 2,
            "assigned_node_id": users[0]['assigned_node_id'] if users else None
        }
        create_success, create_response = self.run_test("Create User", "POST", "users", 200, new_user)
        if not create_success:
            return False

        user_id = create_response.get('id')
        if not user_id:
            self.log_result("User ID Extraction", False, "No user ID returned")
            return False

        # Test UPDATE user
        update_data = {"traffic_limit": 10000000000}  # 10GB
        update_success, _ = self.run_test(
            "Update User", 
            "PUT", 
            f"users/{user_id}", 
            200, 
            update_data
        )

        # Test switch node (if multiple nodes exist)
        if len(users) > 0 and users[0].get('assigned_node_id'):
            switch_success, _ = self.run_test(
                "Switch User Node",
                "POST",
                f"users/{user_id}/switch-node",
                200,
                {"node_id": users[0]['assigned_node_id']}
            )
        else:
            switch_success = True  # Skip if no nodes

        # Test DELETE user
        delete_success, _ = self.run_test("Delete User", "DELETE", f"users/{user_id}", 200)

        return create_success and update_success and delete_success

    def test_traffic_endpoints(self):
        """Test traffic monitoring endpoints"""
        # Test traffic summary
        traffic_success, _ = self.run_test("Traffic Summary", "GET", "traffic", 200)
        
        # Test daily traffic (30 days)
        daily_success, _ = self.run_test("Daily Traffic", "GET", "traffic/daily", 200)
        
        # Test daily traffic with custom days
        custom_success, _ = self.run_test("Custom Daily Traffic", "GET", "traffic/daily?days=7", 200)
        
        return traffic_success and daily_success and custom_success

    def test_license_endpoints(self):
        """Test license management endpoints"""
        # Test GET licenses - should have 1 mock license
        success, licenses = self.run_test("Get Licenses", "GET", "licenses", 200)
        if not success:
            return False

        initial_count = len(licenses)
        self.log_result("Initial Licenses Count", initial_count >= 1, f"Found {initial_count} licenses")

        # Test CREATE license
        create_success, create_response = self.run_test(
            "Create License",
            "POST",
            "licenses",
            200,
            {"expire_days": 30, "max_servers": 5}
        )
        if not create_success:
            return False

        license_id = create_response.get('id')
        license_key = create_response.get('license_key')
        
        if not license_key:
            self.log_result("License Key Extraction", False, "No license key returned")
            return False

        # Test VALIDATE license
        validate_success, _ = self.run_test(
            "Validate License",
            "POST",
            "licenses/validate",
            200,
            {"license_key": license_key}
        )

        # Test REVOKE license  
        revoke_success, _ = self.run_test(
            "Revoke License",
            "DELETE",
            f"licenses/{license_id}",
            200
        )

        return create_success and validate_success and revoke_success

    def test_audit_logs(self):
        """Test audit logs endpoint"""
        # Test GET audit logs
        success, response = self.run_test("Get Audit Logs", "GET", "audit-logs", 200)
        if success:
            # Verify pagination structure
            required_fields = ['total', 'page', 'limit', 'logs']
            missing_fields = [field for field in required_fields if field not in response]
            if missing_fields:
                self.log_result("Audit Logs Structure", False, f"Missing fields: {missing_fields}")
                return False
            else:
                self.log_result("Audit Logs Structure", True, "Pagination structure correct")

        # Test with pagination
        paginated_success, _ = self.run_test("Audit Logs Pagination", "GET", "audit-logs?page=1&limit=5", 200)
        
        return success and paginated_success

    def test_settings_endpoints(self):
        """Test settings endpoints"""
        # Test GET settings
        get_success, settings = self.run_test("Get Settings", "GET", "settings", 200)
        
        # Test UPDATE settings
        update_success, _ = self.run_test(
            "Update Settings",
            "PUT", 
            "settings",
            200,
            {"settings": {"test_key": "test_value"}}
        )
        
        return get_success and update_success

    def test_backup_endpoint(self):
        """Test backup creation"""
        success, response = self.run_test("Create Backup", "POST", "backup", 200)
        if success:
            # Verify backup structure
            required_fields = ['timestamp', 'version', 'nodes', 'users', 'licenses', 'settings']
            missing_fields = [field for field in required_fields if field not in response]
            if missing_fields:
                self.log_result("Backup Structure", False, f"Missing fields: {missing_fields}")
                return False
            else:
                self.log_result("Backup Structure", True, "Backup structure correct")
        
        return success

    def run_all_tests(self):
        """Run all backend API tests"""
        print("🚀 Starting Lightline VPN Panel Backend API Tests")
        print(f"🔗 Testing against: {self.base_url}")
        print("=" * 60)

        # Test root endpoint
        self.test_root_endpoint()

        # Authentication tests
        if not self.test_login():
            print("❌ Login failed - stopping all tests")
            return False

        self.test_auth_me()

        # Core functionality tests
        self.test_dashboard()
        self.test_nodes_crud()
        self.test_users_crud()
        self.test_traffic_endpoints()
        self.test_license_endpoints()
        self.test_audit_logs()
        self.test_settings_endpoints()
        self.test_backup_endpoint()

        # Print summary
        print("\n" + "=" * 60)
        print(f"📊 Test Summary: {self.tests_passed}/{self.tests_run} tests passed")
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        print(f"📈 Success Rate: {success_rate:.1f}%")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All tests passed!")
            return True
        else:
            print("❌ Some tests failed. Check details above.")
            return False

def main():
    tester = LightlineAPITester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())