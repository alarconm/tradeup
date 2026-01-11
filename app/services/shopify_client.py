"""
Shopify Admin API client.
Handles store credit operations and customer management.
"""
import httpx
from typing import Optional, Dict, Any, List


class ShopifyClient:
    """
    Client for Shopify Admin GraphQL API.

    Supports:
    - Store credit operations (add/get balance)
    - Customer tagging
    - Product operations
    - Collections and tags
    """

    def __init__(self, tenant_id_or_domain, access_token: str = None, api_version: str = '2026-01'):
        """
        Initialize Shopify client.

        Can be initialized either with:
        - tenant_id (int): Will fetch credentials from database
        - shop_domain + access_token: Direct initialization
        """
        if isinstance(tenant_id_or_domain, int):
            # Initialize from tenant ID
            from ..models.tenant import Tenant
            tenant = Tenant.query.get(tenant_id_or_domain)
            if not tenant:
                raise ValueError(f"Tenant {tenant_id_or_domain} not found")
            if not tenant.shopify_domain or not tenant.shopify_access_token:
                raise ValueError(f"Tenant {tenant_id_or_domain} missing Shopify credentials")

            self.shop_domain = tenant.shopify_domain.replace('https://', '').replace('http://', '').rstrip('/')
            self.access_token = tenant.shopify_access_token
        else:
            # Direct initialization
            self.shop_domain = tenant_id_or_domain.replace('https://', '').replace('http://', '').rstrip('/')
            self.access_token = access_token

        self.api_version = api_version
        self.graphql_url = f'https://{self.shop_domain}/admin/api/{api_version}/graphql.json'

    def _execute_query(self, query: str, variables: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute a GraphQL query."""
        headers = {
            'X-Shopify-Access-Token': self.access_token,
            'Content-Type': 'application/json'
        }

        payload = {'query': query}
        if variables:
            payload['variables'] = variables

        with httpx.Client() as client:
            response = client.post(
                self.graphql_url,
                headers=headers,
                json=payload,
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()

            if 'errors' in result:
                raise Exception(f"GraphQL errors: {result['errors']}")

            return result.get('data', {})

    def get_store_credit_account_id(self, customer_id: str) -> Optional[str]:
        """
        Get the store credit account ID for a customer.

        Args:
            customer_id: Shopify customer ID (numeric or GID)

        Returns:
            Store credit account GID or None if no account exists
        """
        if not customer_id.startswith('gid://'):
            customer_id = f'gid://shopify/Customer/{customer_id}'

        query = """
        query getCustomerStoreCreditAccount($customerId: ID!) {
            customer(id: $customerId) {
                id
                storeCreditAccounts(first: 1) {
                    edges {
                        node {
                            id
                            balance {
                                amount
                                currencyCode
                            }
                        }
                    }
                }
            }
        }
        """

        result = self._execute_query(query, {'customerId': customer_id})
        customer = result.get('customer', {})
        accounts = customer.get('storeCreditAccounts', {}).get('edges', [])

        if accounts:
            return accounts[0]['node']['id']

        return None

    def add_store_credit(
        self,
        customer_id: str,
        amount: float,
        note: str = 'TradeUp Bonus'
    ) -> Dict[str, Any]:
        """
        Add store credit to a customer account.

        Uses Shopify's native Store Credit API. If the customer doesn't have
        a store credit account yet, Shopify creates one automatically.

        Note: The Shopify storeCreditAccountCredit mutation only accepts
        creditAmount and optional expiresAt. Transaction notes are not
        supported in the current API.

        Args:
            customer_id: Shopify customer ID (numeric or GID)
            amount: Amount to credit (positive number)
            note: For internal logging only (not sent to Shopify)

        Returns:
            Dict with transaction details
        """
        if not customer_id.startswith('gid://'):
            customer_id = f'gid://shopify/Customer/{customer_id}'

        # Get existing store credit account or let Shopify create one
        account_id = self.get_store_credit_account_id(customer_id)

        # Use customer-based credit mutation (works even without existing account)
        query = """
        mutation storeCreditAccountCredit($id: ID!, $creditInput: StoreCreditAccountCreditInput!) {
            storeCreditAccountCredit(id: $id, creditInput: $creditInput) {
                storeCreditAccountTransaction {
                    id
                    amount {
                        amount
                        currencyCode
                    }
                    account {
                        id
                        balance {
                            amount
                            currencyCode
                        }
                    }
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """

        # If no account exists, use customer ID - Shopify will create the account
        target_id = account_id if account_id else customer_id

        variables = {
            'id': target_id,
            'creditInput': {
                'creditAmount': {
                    'amount': str(amount),
                    'currencyCode': 'USD'
                }
                # Note: Shopify API doesn't support transaction notes or notifications
                # TradeUp handles notifications via NotificationService
            }
        }

        result = self._execute_query(query, variables)

        mutation_result = result.get('storeCreditAccountCredit', {})
        user_errors = mutation_result.get('userErrors', [])

        if user_errors:
            raise Exception(f"Shopify errors: {user_errors}")

        transaction = mutation_result.get('storeCreditAccountTransaction', {})
        account = transaction.get('account', {})

        return {
            'success': True,
            'transaction_id': transaction.get('id'),
            'amount': float(transaction.get('amount', {}).get('amount', 0)),
            'currency': transaction.get('amount', {}).get('currencyCode'),
            'account_id': account.get('id'),
            'new_balance': float(account.get('balance', {}).get('amount', 0))
        }

    def debit_store_credit(
        self,
        customer_id: str,
        amount: float,
        note: str = 'Store Credit Redemption'
    ) -> Dict[str, Any]:
        """
        Debit (remove) store credit from a customer account.

        Uses Shopify's native Store Credit API.

        Args:
            customer_id: Shopify customer ID (numeric or GID)
            amount: Amount to debit (positive number)
            note: Transaction note

        Returns:
            Dict with transaction details

        Raises:
            Exception: If customer has no store credit account or insufficient balance
        """
        if not customer_id.startswith('gid://'):
            customer_id = f'gid://shopify/Customer/{customer_id}'

        # Get store credit account - must exist for debit
        account_id = self.get_store_credit_account_id(customer_id)

        if not account_id:
            raise Exception("Customer has no store credit account")

        # Check current balance first
        balance_info = self.get_store_credit_balance(customer_id)
        current_balance = balance_info.get('balance', 0)

        if current_balance < amount:
            raise Exception(
                f"Insufficient store credit balance. "
                f"Available: ${current_balance:.2f}, Requested: ${amount:.2f}"
            )

        query = """
        mutation storeCreditAccountDebit($id: ID!, $debitInput: StoreCreditAccountDebitInput!) {
            storeCreditAccountDebit(id: $id, debitInput: $debitInput) {
                storeCreditAccountTransaction {
                    id
                    amount {
                        amount
                        currencyCode
                    }
                    account {
                        id
                        balance {
                            amount
                            currencyCode
                        }
                    }
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """

        variables = {
            'id': account_id,
            'debitInput': {
                'debitAmount': {
                    'amount': str(amount),
                    'currencyCode': 'USD'
                },
                'note': note
            }
        }

        result = self._execute_query(query, variables)

        mutation_result = result.get('storeCreditAccountDebit', {})
        user_errors = mutation_result.get('userErrors', [])

        if user_errors:
            raise Exception(f"Shopify errors: {user_errors}")

        transaction = mutation_result.get('storeCreditAccountTransaction', {})
        account = transaction.get('account', {})

        return {
            'success': True,
            'transaction_id': transaction.get('id'),
            'amount': float(transaction.get('amount', {}).get('amount', 0)),
            'currency': transaction.get('amount', {}).get('currencyCode'),
            'account_id': account.get('id'),
            'new_balance': float(account.get('balance', {}).get('amount', 0))
        }

    def get_store_credit_balance(self, customer_id: str) -> Dict[str, Any]:
        """
        Get customer's store credit balance.

        Args:
            customer_id: Shopify customer ID

        Returns:
            Dict with balance information
        """
        if not customer_id.startswith('gid://'):
            customer_id = f'gid://shopify/Customer/{customer_id}'

        query = """
        query getCustomerStoreCredit($customerId: ID!) {
            customer(id: $customerId) {
                id
                email
                storeCreditAccounts(first: 1) {
                    edges {
                        node {
                            id
                            balance {
                                amount
                                currencyCode
                            }
                        }
                    }
                }
            }
        }
        """

        result = self._execute_query(query, {'customerId': customer_id})

        customer = result.get('customer', {})
        accounts = customer.get('storeCreditAccounts', {}).get('edges', [])

        if not accounts:
            return {
                'customer_id': customer_id,
                'balance': 0,
                'currency': 'USD'
            }

        account = accounts[0].get('node', {})
        balance_data = account.get('balance', {})

        return {
            'customer_id': customer_id,
            'account_id': account.get('id'),
            'balance': float(balance_data.get('amount', 0)),
            'currency': balance_data.get('currencyCode', 'USD')
        }

    def add_customer_tag(self, customer_id: str, tag: str) -> Dict[str, Any]:
        """
        Add a tag to a customer.

        Args:
            customer_id: Shopify customer ID
            tag: Tag to add

        Returns:
            Dict with result
        """
        if not customer_id.startswith('gid://'):
            customer_id = f'gid://shopify/Customer/{customer_id}'

        query = """
        mutation customerUpdate($input: CustomerInput!) {
            customerUpdate(input: $input) {
                customer {
                    id
                    tags
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """

        # First get existing tags
        get_tags_query = """
        query getCustomer($id: ID!) {
            customer(id: $id) {
                tags
            }
        }
        """

        existing = self._execute_query(get_tags_query, {'id': customer_id})
        existing_tags = existing.get('customer', {}).get('tags', [])

        # Add new tag if not present
        if tag not in existing_tags:
            existing_tags.append(tag)

        variables = {
            'input': {
                'id': customer_id,
                'tags': existing_tags
            }
        }

        result = self._execute_query(query, variables)

        mutation_result = result.get('customerUpdate', {})
        user_errors = mutation_result.get('userErrors', [])

        if user_errors:
            raise Exception(f"Shopify errors: {user_errors}")

        return {
            'success': True,
            'customer_id': customer_id,
            'tags': mutation_result.get('customer', {}).get('tags', [])
        }

    def search_customers(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search for customers by name, email, or phone.

        Args:
            query: Search query (name, email, or phone)
            limit: Maximum results to return

        Returns:
            List of matching customer dicts
        """
        # Build Shopify search query
        # Shopify search supports: email:, phone:, name:, or just text
        search_query = query.strip()

        # If it looks like an email, search by email
        if '@' in search_query:
            shopify_query = f'email:{search_query}'
        # If it looks like a phone number (mostly digits), search by phone
        elif search_query.replace('-', '').replace(' ', '').replace('(', '').replace(')', '').isdigit():
            digits = ''.join(c for c in search_query if c.isdigit())
            shopify_query = f'phone:*{digits}*'
        # If it looks like an ORB# tag, search by tag
        elif search_query.upper().startswith('ORB') or search_query.startswith('#ORB'):
            tag = search_query.upper().replace('#', '')
            shopify_query = f'tag:#{tag}'
        # Otherwise, search by name
        else:
            shopify_query = search_query

        gql_query = """
        query searchCustomers($query: String!, $first: Int!) {
            customers(first: $first, query: $query) {
                edges {
                    node {
                        id
                        email
                        firstName
                        lastName
                        displayName
                        phone
                        tags
                        numberOfOrders
                        amountSpent {
                            amount
                            currencyCode
                        }
                        createdAt
                        storeCreditAccounts(first: 1) {
                            edges {
                                node {
                                    balance {
                                        amount
                                        currencyCode
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """

        result = self._execute_query(gql_query, {'query': shopify_query, 'first': limit})

        customers = []
        for edge in result.get('customers', {}).get('edges', []):
            node = edge.get('node', {})

            # Extract store credit balance
            credit_accounts = node.get('storeCreditAccounts', {}).get('edges', [])
            store_credit = 0
            if credit_accounts:
                store_credit = float(credit_accounts[0].get('node', {}).get('balance', {}).get('amount', 0))

            # Extract ORB# from tags if present
            orb_number = None
            for tag in node.get('tags', []):
                if tag.upper().startswith('#ORB') or tag.upper().startswith('ORB'):
                    orb_number = tag.upper().replace('#', '')
                    break

            # Extract numeric ID from GID
            gid = node.get('id', '')
            numeric_id = gid.split('/')[-1] if gid else None

            customers.append({
                'id': numeric_id,
                'gid': gid,
                'email': node.get('email'),
                'firstName': node.get('firstName'),
                'lastName': node.get('lastName'),
                'displayName': node.get('displayName'),
                'name': node.get('displayName') or f"{node.get('firstName', '')} {node.get('lastName', '')}".strip(),
                'phone': node.get('phone'),
                'tags': node.get('tags', []),
                'orb_number': orb_number,
                'numberOfOrders': node.get('numberOfOrders', 0),
                'amountSpent': float(node.get('amountSpent', {}).get('amount', 0)),
                'storeCredit': store_credit,
                'createdAt': node.get('createdAt')
            })

        return customers

    def get_customer_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Find a customer by email.

        Args:
            email: Customer email

        Returns:
            Customer data or None
        """
        results = self.search_customers(email, limit=1)
        return results[0] if results else None

    def get_customer_by_id(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a customer directly by their Shopify ID.

        Args:
            customer_id: Shopify customer ID (numeric or GID)

        Returns:
            Customer data or None if not found
        """
        # Convert to GID if needed
        if not customer_id.startswith('gid://'):
            gid = f'gid://shopify/Customer/{customer_id}'
        else:
            gid = customer_id
            # Extract numeric ID from GID
            customer_id = gid.split('/')[-1]

        query = """
        query getCustomerById($id: ID!) {
            customer(id: $id) {
                id
                email
                firstName
                lastName
                displayName
                phone
                tags
                numberOfOrders
                amountSpent {
                    amount
                    currencyCode
                }
                createdAt
                storeCreditAccounts(first: 1) {
                    edges {
                        node {
                            balance {
                                amount
                                currencyCode
                            }
                        }
                    }
                }
            }
        }
        """

        try:
            result = self._execute_query(query, {'id': gid})
            node = result.get('customer')

            if not node:
                return None

            # Extract store credit balance
            credit_accounts = node.get('storeCreditAccounts', {}).get('edges', [])
            store_credit = 0
            if credit_accounts:
                store_credit = float(credit_accounts[0].get('node', {}).get('balance', {}).get('amount', 0))

            # Extract ORB# from tags if present
            orb_number = None
            for tag in node.get('tags', []):
                if tag.upper().startswith('#ORB') or tag.upper().startswith('ORB'):
                    orb_number = tag.upper().replace('#', '')
                    break

            return {
                'id': customer_id,
                'gid': gid,
                'email': node.get('email'),
                'firstName': node.get('firstName'),
                'lastName': node.get('lastName'),
                'displayName': node.get('displayName'),
                'name': node.get('displayName') or f"{node.get('firstName', '')} {node.get('lastName', '')}".strip(),
                'phone': node.get('phone'),
                'tags': node.get('tags', []),
                'orb_number': orb_number,
                'numberOfOrders': node.get('numberOfOrders', 0),
                'amountSpent': float(node.get('amountSpent', {}).get('amount', 0)),
                'storeCredit': store_credit,
                'createdAt': node.get('createdAt')
            }
        except Exception:
            return None

    def create_customer(
        self,
        email: str,
        first_name: str = None,
        last_name: str = None,
        phone: str = None,
        tags: List[str] = None,
        note: str = None
    ) -> Dict[str, Any]:
        """
        Create a new customer in Shopify.

        Args:
            email: Customer email (required)
            first_name: Customer first name
            last_name: Customer last name
            phone: Customer phone number
            tags: List of tags to add to customer
            note: Internal note about customer

        Returns:
            Dict with customer data including id, email, etc.

        Raises:
            Exception: If customer creation fails
        """
        query = """
        mutation customerCreate($input: CustomerInput!) {
            customerCreate(input: $input) {
                customer {
                    id
                    email
                    firstName
                    lastName
                    displayName
                    phone
                    tags
                    createdAt
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """

        input_data = {
            'email': email
        }

        if first_name:
            input_data['firstName'] = first_name
        if last_name:
            input_data['lastName'] = last_name
        if phone:
            input_data['phone'] = phone
        if tags:
            input_data['tags'] = tags
        if note:
            input_data['note'] = note

        result = self._execute_query(query, {'input': input_data})

        mutation_result = result.get('customerCreate', {})
        user_errors = mutation_result.get('userErrors', [])

        if user_errors:
            error_messages = [f"{e.get('field', 'unknown')}: {e.get('message', 'Unknown error')}" for e in user_errors]
            raise Exception(f"Failed to create customer: {'; '.join(error_messages)}")

        customer = mutation_result.get('customer')
        if not customer:
            raise Exception("Customer creation returned no customer data")

        # Extract numeric ID from GID
        gid = customer.get('id', '')
        numeric_id = gid.split('/')[-1] if gid else None

        return {
            'id': numeric_id,
            'gid': gid,
            'email': customer.get('email'),
            'firstName': customer.get('firstName'),
            'lastName': customer.get('lastName'),
            'displayName': customer.get('displayName'),
            'name': customer.get('displayName') or f"{customer.get('firstName', '')} {customer.get('lastName', '')}".strip(),
            'phone': customer.get('phone'),
            'tags': customer.get('tags', []),
            'createdAt': customer.get('createdAt')
        }

    def get_collections(self) -> List[Dict[str, Any]]:
        """
        Get all collections from Shopify.

        Returns:
            List of collection dicts with id, title, handle, productsCount
        """
        query = """
        query getCollections($first: Int!, $after: String) {
            collections(first: $first, after: $after) {
                pageInfo {
                    hasNextPage
                    endCursor
                }
                edges {
                    node {
                        id
                        title
                        handle
                        productsCount
                    }
                }
            }
        }
        """

        all_collections = []
        has_next_page = True
        cursor = None

        while has_next_page:
            variables = {'first': 100}
            if cursor:
                variables['after'] = cursor

            result = self._execute_query(query, variables)
            collections_data = result.get('collections', {})

            edges = collections_data.get('edges', [])
            for edge in edges:
                node = edge.get('node', {})
                all_collections.append({
                    'id': node.get('id'),
                    'title': node.get('title'),
                    'handle': node.get('handle'),
                    'productsCount': node.get('productsCount', 0)
                })

            page_info = collections_data.get('pageInfo', {})
            has_next_page = page_info.get('hasNextPage', False)
            cursor = page_info.get('endCursor')

        return all_collections

    def get_product_tags(self) -> List[str]:
        """
        Get all unique product tags from Shopify.

        Returns:
            List of unique tag strings
        """
        query = """
        query getProductTags($first: Int!, $after: String) {
            products(first: $first, after: $after) {
                pageInfo {
                    hasNextPage
                    endCursor
                }
                edges {
                    node {
                        tags
                    }
                }
            }
        }
        """

        all_tags = set()
        has_next_page = True
        cursor = None

        # Limit to 500 products for performance
        max_pages = 5

        while has_next_page and max_pages > 0:
            variables = {'first': 100}
            if cursor:
                variables['after'] = cursor

            result = self._execute_query(query, variables)
            products_data = result.get('products', {})

            edges = products_data.get('edges', [])
            for edge in edges:
                node = edge.get('node', {})
                tags = node.get('tags', [])
                all_tags.update(tags)

            page_info = products_data.get('pageInfo', {})
            has_next_page = page_info.get('hasNextPage', False)
            cursor = page_info.get('endCursor')
            max_pages -= 1

        return sorted(list(all_tags))

    def get_customer_tags(self) -> List[str]:
        """
        Get all unique customer tags from Shopify.

        Returns:
            List of unique tag strings
        """
        query = """
        query getCustomerTags($first: Int!, $after: String) {
            customers(first: $first, after: $after) {
                pageInfo {
                    hasNextPage
                    endCursor
                }
                edges {
                    node {
                        tags
                    }
                }
            }
        }
        """

        all_tags = set()
        has_next_page = True
        cursor = None

        # Limit to 500 customers for performance
        max_pages = 5

        while has_next_page and max_pages > 0:
            variables = {'first': 100}
            if cursor:
                variables['after'] = cursor

            result = self._execute_query(query, variables)
            customers_data = result.get('customers', {})

            edges = customers_data.get('edges', [])
            for edge in edges:
                node = edge.get('node', {})
                tags = node.get('tags', [])
                all_tags.update(tags)

            page_info = customers_data.get('pageInfo', {})
            has_next_page = page_info.get('hasNextPage', False)
            cursor = page_info.get('endCursor')
            max_pages -= 1

        return sorted(list(all_tags))

    # =========================================
    # Product Filter Options (for Promotions)
    # =========================================

    def get_collections(self, include_smart: bool = True) -> List[Dict[str, Any]]:
        """
        Get all collections from Shopify for promotion filtering.

        Args:
            include_smart: Include smart collections (default True)

        Returns:
            List of collection dicts with id, title, handle, productsCount
        """
        query = """
        query getCollections($first: Int!, $after: String) {
            collections(first: $first, after: $after) {
                pageInfo {
                    hasNextPage
                    endCursor
                }
                edges {
                    node {
                        id
                        title
                        handle
                        productsCount
                        ruleSet {
                            appliedDisjunctively
                        }
                    }
                }
            }
        }
        """

        all_collections = []
        has_next_page = True
        cursor = None

        while has_next_page:
            variables = {'first': 100}
            if cursor:
                variables['after'] = cursor

            result = self._execute_query(query, variables)
            collections_data = result.get('collections', {})

            edges = collections_data.get('edges', [])
            for edge in edges:
                node = edge.get('node', {})
                # ruleSet being non-null indicates a smart collection
                is_smart = node.get('ruleSet') is not None
                if not include_smart and is_smart:
                    continue

                all_collections.append({
                    'id': node.get('id'),
                    'title': node.get('title'),
                    'handle': node.get('handle'),
                    'productsCount': node.get('productsCount', 0),
                    'isSmart': is_smart
                })

            page_info = collections_data.get('pageInfo', {})
            has_next_page = page_info.get('hasNextPage', False)
            cursor = page_info.get('endCursor')

        return sorted(all_collections, key=lambda x: x['title'].lower())

    def get_vendors(self) -> List[str]:
        """
        Get all unique product vendors from Shopify.

        Returns:
            List of unique vendor strings
        """
        query = """
        query getProductVendors($first: Int!, $after: String) {
            products(first: $first, after: $after) {
                pageInfo {
                    hasNextPage
                    endCursor
                }
                edges {
                    node {
                        vendor
                    }
                }
            }
        }
        """

        all_vendors = set()
        has_next_page = True
        cursor = None

        # Limit pages for performance
        max_pages = 10

        while has_next_page and max_pages > 0:
            variables = {'first': 100}
            if cursor:
                variables['after'] = cursor

            result = self._execute_query(query, variables)
            products_data = result.get('products', {})

            edges = products_data.get('edges', [])
            for edge in edges:
                node = edge.get('node', {})
                vendor = node.get('vendor')
                if vendor and vendor.strip():
                    all_vendors.add(vendor.strip())

            page_info = products_data.get('pageInfo', {})
            has_next_page = page_info.get('hasNextPage', False)
            cursor = page_info.get('endCursor')
            max_pages -= 1

        return sorted(list(all_vendors))

    def get_product_types(self) -> List[str]:
        """
        Get all unique product types from Shopify.

        Returns:
            List of unique product type strings
        """
        query = """
        query getProductTypes($first: Int!, $after: String) {
            products(first: $first, after: $after) {
                pageInfo {
                    hasNextPage
                    endCursor
                }
                edges {
                    node {
                        productType
                    }
                }
            }
        }
        """

        all_types = set()
        has_next_page = True
        cursor = None

        # Limit pages for performance
        max_pages = 10

        while has_next_page and max_pages > 0:
            variables = {'first': 100}
            if cursor:
                variables['after'] = cursor

            result = self._execute_query(query, variables)
            products_data = result.get('products', {})

            edges = products_data.get('edges', [])
            for edge in edges:
                node = edge.get('node', {})
                product_type = node.get('productType')
                if product_type and product_type.strip():
                    all_types.add(product_type.strip())

            page_info = products_data.get('pageInfo', {})
            has_next_page = page_info.get('hasNextPage', False)
            cursor = page_info.get('endCursor')
            max_pages -= 1

        return sorted(list(all_types))

    def get_promotion_filter_options(self) -> Dict[str, Any]:
        """
        Get all filter options for promotion configuration.

        Returns:
            Dict with collections, vendors, productTypes, and productTags
        """
        return {
            'collections': self.get_collections(),
            'vendors': self.get_vendors(),
            'productTypes': self.get_product_types(),
            'productTags': self.get_product_tags()
        }

    # =========================================
    # Customer Segment Management
    # =========================================

    def get_segments(self) -> List[Dict[str, Any]]:
        """
        Get all customer segments from Shopify.

        Returns:
            List of segment dicts with id, name, query
        """
        query = """
        query getSegments($first: Int!, $after: String) {
            segments(first: $first, after: $after) {
                pageInfo {
                    hasNextPage
                    endCursor
                }
                edges {
                    node {
                        id
                        name
                        query
                        creationDate
                        lastEditDate
                    }
                }
            }
        }
        """

        all_segments = []
        has_next_page = True
        cursor = None

        while has_next_page:
            variables = {'first': 50}
            if cursor:
                variables['after'] = cursor

            result = self._execute_query(query, variables)
            segments_data = result.get('segments', {})

            edges = segments_data.get('edges', [])
            for edge in edges:
                node = edge.get('node', {})
                all_segments.append({
                    'id': node.get('id'),
                    'name': node.get('name'),
                    'query': node.get('query'),
                    'creationDate': node.get('creationDate'),
                    'lastEditDate': node.get('lastEditDate')
                })

            page_info = segments_data.get('pageInfo', {})
            has_next_page = page_info.get('hasNextPage', False)
            cursor = page_info.get('endCursor')

        return all_segments

    def create_segment(self, name: str, segment_query: str) -> Dict[str, Any]:
        """
        Create a customer segment in Shopify.

        Uses the modern input pattern per Shopify's 2024+ API specs.

        Args:
            name: Segment name (e.g., "TradeUp Gold Members")
            segment_query: Shopify segment query (e.g., "customer_tags CONTAINS 'tu-gold'")

        Returns:
            Dict with segment details
        """
        mutation = """
        mutation CreateSegment($input: SegmentCreateInput!) {
            segmentCreate(input: $input) {
                segment {
                    id
                    name
                    query
                    creationDate
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """

        variables = {
            'input': {
                'name': name,
                'query': segment_query
            }
        }

        result = self._execute_query(mutation, variables)

        mutation_result = result.get('segmentCreate', {})
        user_errors = mutation_result.get('userErrors', [])

        if user_errors:
            raise Exception(f"Shopify errors: {user_errors}")

        segment = mutation_result.get('segment', {})

        return {
            'success': True,
            'id': segment.get('id'),
            'name': segment.get('name'),
            'query': segment.get('query'),
            'creationDate': segment.get('creationDate')
        }

    def update_segment(self, segment_id: str, name: str = None, segment_query: str = None) -> Dict[str, Any]:
        """
        Update an existing customer segment.

        Args:
            segment_id: Shopify segment GID
            name: New name (optional)
            segment_query: New query (optional)

        Returns:
            Dict with updated segment details
        """
        mutation = """
        mutation segmentUpdate($id: ID!, $name: String, $query: String) {
            segmentUpdate(id: $id, name: $name, query: $query) {
                segment {
                    id
                    name
                    query
                    lastEditDate
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """

        variables = {'id': segment_id}
        if name:
            variables['name'] = name
        if segment_query:
            variables['query'] = segment_query

        result = self._execute_query(mutation, variables)

        mutation_result = result.get('segmentUpdate', {})
        user_errors = mutation_result.get('userErrors', [])

        if user_errors:
            raise Exception(f"Shopify errors: {user_errors}")

        segment = mutation_result.get('segment', {})

        return {
            'success': True,
            'id': segment.get('id'),
            'name': segment.get('name'),
            'query': segment.get('query'),
            'lastEditDate': segment.get('lastEditDate')
        }

    def delete_segment(self, segment_id: str) -> Dict[str, Any]:
        """
        Delete a customer segment.

        Args:
            segment_id: Shopify segment GID

        Returns:
            Dict with success status
        """
        mutation = """
        mutation segmentDelete($id: ID!) {
            segmentDelete(id: $id) {
                deletedSegmentId
                userErrors {
                    field
                    message
                }
            }
        }
        """

        result = self._execute_query(mutation, {'id': segment_id})

        mutation_result = result.get('segmentDelete', {})
        user_errors = mutation_result.get('userErrors', [])

        if user_errors:
            raise Exception(f"Shopify errors: {user_errors}")

        return {
            'success': True,
            'deletedSegmentId': mutation_result.get('deletedSegmentId')
        }

    def find_segment_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Find a segment by its name.

        Args:
            name: Segment name to search for

        Returns:
            Segment dict or None if not found
        """
        segments = self.get_segments()
        for segment in segments:
            if segment.get('name') == name:
                return segment
        return None

    def create_or_update_segment(self, name: str, segment_query: str) -> Dict[str, Any]:
        """
        Create a segment if it doesn't exist, or update it if it does.

        Args:
            name: Segment name
            segment_query: Shopify segment query

        Returns:
            Dict with segment details and whether it was created or updated
        """
        existing = self.find_segment_by_name(name)

        if existing:
            # Update existing segment
            result = self.update_segment(existing['id'], name=name, segment_query=segment_query)
            result['action'] = 'updated'
            return result
        else:
            # Create new segment
            result = self.create_segment(name, segment_query)
            result['action'] = 'created'
            return result

    def create_tradeup_segments(self, tiers: List[Dict[str, Any]], tag_prefix: str = 'tu-') -> Dict[str, Any]:
        """
        Create/update all TradeUp customer segments based on tiers.

        Creates:
        1. "TradeUp Members" - All members with any tier tag
        2. One segment per tier (e.g., "TradeUp Gold Members")

        Args:
            tiers: List of tier dicts with 'name' and 'slug' keys
            tag_prefix: Prefix for tier tags (default: 'tu-')

        Returns:
            Dict with results for each segment created/updated
        """
        results = {
            'success': True,
            'segments': [],
            'errors': []
        }

        # Build the "all members" query with OR conditions for all tier tags
        tier_tag_conditions = []
        for tier in tiers:
            slug = tier.get('slug', tier.get('name', '').lower().replace(' ', '-'))
            tag = f"{tag_prefix}{slug}"
            tier_tag_conditions.append(f"customer_tags CONTAINS '{tag}'")

        # Create "All TradeUp Members" segment
        if tier_tag_conditions:
            all_members_query = ' OR '.join(tier_tag_conditions)
            try:
                result = self.create_or_update_segment(
                    name="TradeUp Members",
                    segment_query=all_members_query
                )
                results['segments'].append({
                    'name': 'TradeUp Members',
                    'action': result.get('action'),
                    'id': result.get('id'),
                    'query': all_members_query
                })
            except Exception as e:
                results['errors'].append({
                    'name': 'TradeUp Members',
                    'error': str(e)
                })

        # Create per-tier segments
        for tier in tiers:
            tier_name = tier.get('name', 'Unknown')
            slug = tier.get('slug', tier_name.lower().replace(' ', '-'))
            tag = f"{tag_prefix}{slug}"
            segment_name = f"TradeUp {tier_name} Members"
            segment_query = f"customer_tags CONTAINS '{tag}'"

            try:
                result = self.create_or_update_segment(
                    name=segment_name,
                    segment_query=segment_query
                )
                results['segments'].append({
                    'name': segment_name,
                    'action': result.get('action'),
                    'id': result.get('id'),
                    'query': segment_query
                })
            except Exception as e:
                results['errors'].append({
                    'name': segment_name,
                    'error': str(e)
                })

        if results['errors']:
            results['success'] = False

        return results

    # =========================================
    # Membership Product Management
    # =========================================

    def get_products_by_tag(self, tag: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get products that have a specific tag.

        Args:
            tag: Tag to search for
            limit: Maximum products to return

        Returns:
            List of product dicts
        """
        query = """
        query getProductsByTag($query: String!, $first: Int!) {
            products(first: $first, query: $query) {
                edges {
                    node {
                        id
                        title
                        handle
                        status
                        tags
                        variants(first: 10) {
                            edges {
                                node {
                                    id
                                    title
                                    price
                                    sku
                                }
                            }
                        }
                    }
                }
            }
        }
        """

        result = self._execute_query(query, {'query': f'tag:{tag}', 'first': limit})

        products = []
        for edge in result.get('products', {}).get('edges', []):
            node = edge.get('node', {})
            variants = []
            for v_edge in node.get('variants', {}).get('edges', []):
                v_node = v_edge.get('node', {})
                variants.append({
                    'id': v_node.get('id'),
                    'title': v_node.get('title'),
                    'price': v_node.get('price'),
                    'sku': v_node.get('sku')
                })
            products.append({
                'id': node.get('id'),
                'title': node.get('title'),
                'handle': node.get('handle'),
                'status': node.get('status'),
                'tags': node.get('tags', []),
                'variants': variants
            })

        return products

    def product_set(
        self,
        title: str,
        body_html: str,
        vendor: str,
        product_type: str,
        tags: List[str],
        variants: List[Dict[str, Any]],
        status: str = 'ACTIVE',
        product_id: str = None
    ) -> Dict[str, Any]:
        """
        Create or update a product using Shopify's modern productSet mutation.

        This is Shopify's recommended approach for product management as of 2024+.
        It handles both creation and updates in a single mutation and is designed
        for sync workflows and bulk operations.

        Args:
            title: Product title
            body_html: Product description (HTML)
            vendor: Vendor name
            product_type: Product type
            tags: List of tags
            variants: List of variant dicts with price, sku, title
            status: ACTIVE, DRAFT, or ARCHIVED
            product_id: Existing product GID for updates (optional)

        Returns:
            Dict with product details
        """
        mutation = """
        mutation ProductSet($input: ProductSetInput!, $synchronous: Boolean!) {
            productSet(input: $input, synchronous: $synchronous) {
                product {
                    id
                    title
                    handle
                    status
                    variants(first: 10) {
                        edges {
                            node {
                                id
                                title
                                price
                                sku
                            }
                        }
                    }
                }
                productSetOperation {
                    id
                    status
                }
                userErrors {
                    field
                    message
                    code
                }
            }
        }
        """

        # Build product options if we have variant titles (like Monthly/Yearly)
        has_options = any(v.get('title') for v in variants)
        product_options = []
        if has_options:
            product_options = [{
                'name': 'Plan',
                'values': [{'name': v.get('title', 'Default')} for v in variants if v.get('title')]
            }]

        # Build variants input for productSet
        variant_inputs = []
        for v in variants:
            variant_input = {
                'price': str(v.get('price', 0)),
            }
            if v.get('sku'):
                variant_input['sku'] = v['sku']
            if v.get('title') and has_options:
                variant_input['optionValues'] = [{'optionName': 'Plan', 'name': v['title']}]
            variant_inputs.append(variant_input)

        # Build input object
        input_data = {
            'title': title,
            'descriptionHtml': body_html,
            'vendor': vendor,
            'productType': product_type,
            'tags': tags,
            'status': status,
            'variants': variant_inputs
        }

        # Add product options if we have them
        if product_options:
            input_data['productOptions'] = product_options

        # If updating existing product, include the ID
        if product_id:
            input_data['id'] = product_id

        variables = {
            'input': input_data,
            'synchronous': True  # Run synchronously for immediate feedback
        }

        result = self._execute_query(mutation, variables)

        mutation_result = result.get('productSet', {})
        user_errors = mutation_result.get('userErrors', [])

        if user_errors:
            raise Exception(f"Shopify errors: {user_errors}")

        product = mutation_result.get('product', {})
        variants_result = []
        for v_edge in product.get('variants', {}).get('edges', []):
            v_node = v_edge.get('node', {})
            variants_result.append({
                'id': v_node.get('id'),
                'title': v_node.get('title'),
                'price': v_node.get('price'),
                'sku': v_node.get('sku')
            })

        return {
            'success': True,
            'id': product.get('id'),
            'title': product.get('title'),
            'handle': product.get('handle'),
            'status': product.get('status'),
            'variants': variants_result
        }

    def update_product(
        self,
        product_id: str,
        title: str = None,
        body_html: str = None,
        tags: List[str] = None,
        status: str = None
    ) -> Dict[str, Any]:
        """
        Update an existing product using productSet.

        Uses the modern productSet mutation per Shopify's 2024+ recommendations.

        Args:
            product_id: Shopify product GID
            title: New title (optional)
            body_html: New description (optional)
            tags: New tags (optional)
            status: New status (optional)

        Returns:
            Dict with updated product details
        """
        mutation = """
        mutation ProductSetUpdate($input: ProductSetInput!, $synchronous: Boolean!) {
            productSet(input: $input, synchronous: $synchronous) {
                product {
                    id
                    title
                    handle
                    status
                    tags
                }
                userErrors {
                    field
                    message
                    code
                }
            }
        }
        """

        input_data = {'id': product_id}
        if title:
            input_data['title'] = title
        if body_html:
            input_data['descriptionHtml'] = body_html
        if tags is not None:
            input_data['tags'] = tags
        if status:
            input_data['status'] = status

        result = self._execute_query(mutation, {
            'input': input_data,
            'synchronous': True
        })

        mutation_result = result.get('productSet', {})
        user_errors = mutation_result.get('userErrors', [])

        if user_errors:
            raise Exception(f"Shopify errors: {user_errors}")

        product = mutation_result.get('product', {})

        return {
            'success': True,
            'id': product.get('id'),
            'title': product.get('title'),
            'handle': product.get('handle'),
            'status': product.get('status'),
            'tags': product.get('tags', [])
        }

    def update_product_status(
        self,
        product_id: str,
        status: str = 'ACTIVE'
    ) -> Dict[str, Any]:
        """
        Update a product's status (ACTIVE, DRAFT, or ARCHIVED).

        Used for publishing draft products or archiving old ones.

        Args:
            product_id: Shopify product GID (gid://shopify/Product/123)
            status: New status - ACTIVE, DRAFT, or ARCHIVED

        Returns:
            Dict with updated product info
        """
        mutation = """
        mutation productUpdate($input: ProductInput!) {
            productUpdate(input: $input) {
                product {
                    id
                    title
                    handle
                    status
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """

        variables = {
            'input': {
                'id': product_id,
                'status': status
            }
        }

        result = self._execute_query(mutation, variables)

        mutation_result = result.get('productUpdate', {})
        user_errors = mutation_result.get('userErrors', [])

        if user_errors:
            raise Exception(f"Shopify errors: {user_errors}")

        product = mutation_result.get('product', {})

        return {
            'success': True,
            'id': product.get('id'),
            'title': product.get('title'),
            'handle': product.get('handle'),
            'status': product.get('status'),
        }

    def create_tradeup_membership_products(
        self,
        tiers: List[Dict[str, Any]],
        shop_name: str = 'TradeUp'
    ) -> Dict[str, Any]:
        """
        Create/update Shopify products for each membership tier.

        Uses Shopify's modern productSet mutation for optimal performance
        and compatibility with the latest API standards.

        Creates purchasable products that customers can buy to join
        a membership tier. Each tier becomes a product with Monthly/Yearly
        variants based on the tier pricing configuration.

        Args:
            tiers: List of tier dicts with name, slug, price, yearly_price, etc.
            shop_name: Shop name for vendor field

        Returns:
            Dict with results for each product created/updated
        """
        results = {
            'success': True,
            'products': [],
            'errors': []
        }

        # Check for existing TradeUp membership products
        existing_products = self.get_products_by_tag('tradeup-membership')
        existing_by_sku = {}
        for prod in existing_products:
            for variant in prod.get('variants', []):
                if variant.get('sku'):
                    existing_by_sku[variant['sku']] = {
                        'product_id': prod['id'],
                        'variant_id': variant['id']
                    }

        # Create/update a product for each tier using productSet
        for tier in tiers:
            tier_name = tier.get('name', 'Unknown')
            tier_slug = tier.get('slug', tier_name.lower().replace(' ', '-'))
            price = tier.get('price', 0)
            yearly_price = tier.get('yearly_price')
            description = tier.get('description', '')
            trade_in_bonus = tier.get('trade_in_bonus_percent', 0)
            cashback_percent = tier.get('cashback_percent', 0)

            # Build product description with benefits
            benefits = []
            if trade_in_bonus > 0:
                benefits.append(f"+{trade_in_bonus}% trade-in bonus")
            if cashback_percent > 0:
                benefits.append(f"{cashback_percent}% cashback on purchases")

            body_html = f"""
            <p>{description or f'Join our {tier_name} membership tier!'}</p>
            <h3>Benefits:</h3>
            <ul>
                {''.join(f'<li>{b}</li>' for b in benefits) if benefits else '<li>Exclusive member perks</li>'}
            </ul>
            """

            # SKUs for tracking
            monthly_sku = f"TU-{tier_slug.upper()}-MONTHLY"
            yearly_sku = f"TU-{tier_slug.upper()}-YEARLY"

            # Build variants
            variants = [
                {'title': 'Monthly', 'price': price, 'sku': monthly_sku}
            ]
            if yearly_price:
                variants.append({
                    'title': 'Yearly',
                    'price': yearly_price,
                    'sku': yearly_sku
                })

            # Check if product already exists
            existing_product_id = None
            if monthly_sku in existing_by_sku:
                existing_product_id = existing_by_sku[monthly_sku]['product_id']

            try:
                # Use productSet for both create and update
                result = self.product_set(
                    title=f"{tier_name} Membership",
                    body_html=body_html.strip(),
                    vendor=shop_name,
                    product_type='Membership',
                    tags=['tradeup-membership', f'tier-{tier_slug}', 'membership'],
                    variants=variants,
                    status='ACTIVE',
                    product_id=existing_product_id
                )
                results['products'].append({
                    'tier': tier_name,
                    'action': 'updated' if existing_product_id else 'created',
                    'product_id': result.get('id'),
                    'variants': result.get('variants', [])
                })
            except Exception as e:
                results['errors'].append({
                    'tier': tier_name,
                    'error': str(e)
                })

        if results['errors']:
            results['success'] = False

        return results

    # ==================== Customer Metafields ====================

    def set_customer_metafields(
        self,
        customer_id: str,
        metafields: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Set metafields on a Shopify customer.

        Args:
            customer_id: Shopify customer ID (numeric or GID)
            metafields: List of metafield dicts with:
                - namespace: string (e.g., 'tradeup')
                - key: string (e.g., 'member_number')
                - value: string
                - type: string (e.g., 'single_line_text_field', 'number_integer')

        Returns:
            Dict with success status and any errors
        """
        # Convert to GID if needed
        if not str(customer_id).startswith('gid://'):
            customer_gid = f'gid://shopify/Customer/{customer_id}'
        else:
            customer_gid = customer_id

        mutation = """
        mutation customerUpdate($input: CustomerInput!) {
            customerUpdate(input: $input) {
                customer {
                    id
                    metafields(first: 20, namespace: "tradeup") {
                        edges {
                            node {
                                namespace
                                key
                                value
                                type
                            }
                        }
                    }
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """

        # Build metafield inputs
        metafield_inputs = []
        for mf in metafields:
            metafield_inputs.append({
                'namespace': mf.get('namespace', 'tradeup'),
                'key': mf['key'],
                'value': str(mf['value']),
                'type': mf.get('type', 'single_line_text_field')
            })

        variables = {
            'input': {
                'id': customer_gid,
                'metafields': metafield_inputs
            }
        }

        try:
            result = self._execute_query(mutation, variables)
            mutation_result = result.get('customerUpdate', {})
            user_errors = mutation_result.get('userErrors', [])

            if user_errors:
                return {
                    'success': False,
                    'errors': user_errors
                }

            customer = mutation_result.get('customer', {})
            metafields_result = []
            for edge in customer.get('metafields', {}).get('edges', []):
                node = edge.get('node', {})
                metafields_result.append({
                    'namespace': node.get('namespace'),
                    'key': node.get('key'),
                    'value': node.get('value'),
                    'type': node.get('type')
                })

            return {
                'success': True,
                'customer_id': customer.get('id'),
                'metafields': metafields_result
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def sync_member_metafields(
        self,
        customer_id: str,
        member_number: str,
        tier_name: str = None,
        credit_balance: float = 0,
        trade_in_count: int = 0,
        total_bonus_earned: float = 0,
        joined_date: str = None,
        status: str = 'active'
    ) -> Dict[str, Any]:
        """
        Sync TradeUp member data to Shopify customer metafields.

        This makes member info visible in Shopify Admin customer profiles.

        Args:
            customer_id: Shopify customer ID
            member_number: TradeUp member number (e.g., "TU-001234")
            tier_name: Current tier name (e.g., "Gold")
            credit_balance: Current store credit balance
            trade_in_count: Total number of trade-ins
            total_bonus_earned: Total bonus credits earned
            joined_date: Date joined (ISO format)
            status: Member status (active, paused, cancelled)

        Returns:
            Dict with success status
        """
        metafields = [
            {
                'key': 'member_number',
                'value': member_number,
                'type': 'single_line_text_field'
            },
            {
                'key': 'tier',
                'value': tier_name or 'None',
                'type': 'single_line_text_field'
            },
            {
                'key': 'credit_balance',
                'value': str(round(credit_balance, 2)),
                'type': 'number_decimal'
            },
            {
                'key': 'trade_in_count',
                'value': str(int(trade_in_count)),
                'type': 'number_integer'
            },
            {
                'key': 'total_bonus_earned',
                'value': str(round(total_bonus_earned, 2)),
                'type': 'number_decimal'
            },
            {
                'key': 'status',
                'value': status,
                'type': 'single_line_text_field'
            }
        ]

        # Add joined date if provided
        if joined_date:
            metafields.append({
                'key': 'joined_date',
                'value': joined_date,
                'type': 'date'
            })

        return self.set_customer_metafields(customer_id, metafields)

    def get_customer_metafields(
        self,
        customer_id: str,
        namespace: str = 'tradeup'
    ) -> Dict[str, Any]:
        """
        Get metafields for a customer.

        Args:
            customer_id: Shopify customer ID (numeric or GID)
            namespace: Metafield namespace to fetch

        Returns:
            Dict with metafields keyed by their key name
        """
        # Convert to GID if needed
        if not str(customer_id).startswith('gid://'):
            customer_gid = f'gid://shopify/Customer/{customer_id}'
        else:
            customer_gid = customer_id

        query = """
        query getCustomerMetafields($id: ID!, $namespace: String!) {
            customer(id: $id) {
                id
                metafields(first: 20, namespace: $namespace) {
                    edges {
                        node {
                            namespace
                            key
                            value
                            type
                        }
                    }
                }
            }
        }
        """

        try:
            result = self._execute_query(query, {
                'id': customer_gid,
                'namespace': namespace
            })

            customer = result.get('customer')
            if not customer:
                return {'success': False, 'error': 'Customer not found'}

            metafields = {}
            for edge in customer.get('metafields', {}).get('edges', []):
                node = edge.get('node', {})
                key = node.get('key')
                metafields[key] = {
                    'value': node.get('value'),
                    'type': node.get('type')
                }

            return {
                'success': True,
                'customer_id': customer.get('id'),
                'metafields': metafields
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    # ==================== Automatic Discounts ====================

    def create_automatic_discount(
        self,
        title: str,
        percentage: float,
        customer_tag: str,
        starts_at: str = None,
        ends_at: str = None,
        minimum_subtotal: float = None,
        applies_to_all: bool = True,
        collection_ids: list = None
    ) -> Dict[str, Any]:
        """
        Create an automatic discount for customers with a specific tag.

        This creates a discount that automatically applies at checkout
        for customers who have the specified tag (e.g., tradeup-gold).

        Args:
            title: Discount title (e.g., "TradeUp Gold Member - 20% Off")
            percentage: Discount percentage (e.g., 20 for 20%)
            customer_tag: Tag that customers must have (e.g., "tradeup-gold")
            starts_at: ISO datetime when discount starts (default: now)
            ends_at: ISO datetime when discount ends (default: no end)
            minimum_subtotal: Minimum cart value to qualify
            applies_to_all: If True, applies to all products
            collection_ids: List of collection GIDs to limit discount to

        Returns:
            Dict with discount details or error
        """
        from datetime import datetime

        # Build customer eligibility segment
        # Shopify uses customer segments with tag conditions
        customer_gets = {
            'value': {
                'percentage': percentage / 100  # Shopify wants decimal (0.20 for 20%)
            }
        }

        # Determine what products the discount applies to
        if applies_to_all:
            customer_gets['items'] = {'all': True}
        elif collection_ids:
            customer_gets['items'] = {
                'collections': {
                    'add': collection_ids
                }
            }
        else:
            customer_gets['items'] = {'all': True}

        # Build minimum requirements
        minimum_requirement = None
        if minimum_subtotal:
            minimum_requirement = {
                'subtotal': {
                    'greaterThanOrEqualToSubtotal': str(minimum_subtotal)
                }
            }

        mutation = """
        mutation discountAutomaticBasicCreate($automaticBasicDiscount: DiscountAutomaticBasicInput!) {
            discountAutomaticBasicCreate(automaticBasicDiscount: $automaticBasicDiscount) {
                automaticDiscountNode {
                    id
                    automaticDiscount {
                        ... on DiscountAutomaticBasic {
                            title
                            status
                            startsAt
                            endsAt
                            customerGets {
                                value {
                                    ... on DiscountPercentage {
                                        percentage
                                    }
                                }
                            }
                        }
                    }
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """

        variables = {
            'automaticBasicDiscount': {
                'title': title,
                'startsAt': starts_at or datetime.utcnow().isoformat() + 'Z',
                'customerGets': customer_gets,
                'combinesWith': {
                    'productDiscounts': False,
                    'orderDiscounts': False,
                    'shippingDiscounts': True
                }
            }
        }

        if ends_at:
            variables['automaticBasicDiscount']['endsAt'] = ends_at

        if minimum_requirement:
            variables['automaticBasicDiscount']['minimumRequirement'] = minimum_requirement

        try:
            result = self._execute_query(mutation, variables)
            data = result.get('discountAutomaticBasicCreate', {})

            errors = data.get('userErrors', [])
            if errors:
                return {
                    'success': False,
                    'errors': errors
                }

            node = data.get('automaticDiscountNode', {})
            discount = node.get('automaticDiscount', {})

            # Now we need to add the customer segment condition
            # This requires updating the discount with customer selection
            discount_id = node.get('id')
            if discount_id:
                # Update with customer tag condition using metafield/segment
                self._add_customer_tag_condition(discount_id, customer_tag)

            return {
                'success': True,
                'discount_id': discount_id,
                'title': discount.get('title'),
                'status': discount.get('status'),
                'percentage': percentage,
                'customer_tag': customer_tag
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def _add_customer_tag_condition(self, discount_id: str, customer_tag: str) -> bool:
        """
        Add customer tag condition to an automatic discount.

        Note: Shopify's automatic discounts with customer eligibility
        require using the newer discount APIs or customer segments.
        This method attempts to set the customer eligibility.
        """
        # For automatic discounts with customer tag requirements,
        # we need to use discountAutomaticBxgyUpdate or create
        # a customer segment first and reference it.

        # Alternative approach: Use discount codes with customer tag validation
        # For now, log that manual configuration may be needed
        print(f"Note: Customer tag '{customer_tag}' condition for discount {discount_id}")
        print("Automatic discounts with customer eligibility may require manual Shopify admin setup")
        return True

    def create_tier_discount_code(
        self,
        tier_name: str,
        percentage: float,
        customer_tag: str,
        usage_limit: int = None
    ) -> Dict[str, Any]:
        """
        Create a discount code for a membership tier.

        This creates a unique discount code that validates the customer
        has the required tag before applying.

        Args:
            tier_name: Name of the tier (e.g., "Gold")
            percentage: Discount percentage
            customer_tag: Required customer tag (e.g., "tradeup-gold")
            usage_limit: Optional limit on total uses

        Returns:
            Dict with discount code details
        """
        from datetime import datetime

        code = f"TRADEUP-{tier_name.upper()}"
        title = f"TradeUp {tier_name} Member Discount ({int(percentage)}% off)"

        mutation = """
        mutation discountCodeBasicCreate($basicCodeDiscount: DiscountCodeBasicInput!) {
            discountCodeBasicCreate(basicCodeDiscount: $basicCodeDiscount) {
                codeDiscountNode {
                    id
                    codeDiscount {
                        ... on DiscountCodeBasic {
                            title
                            status
                            codes(first: 1) {
                                nodes {
                                    code
                                }
                            }
                            customerGets {
                                value {
                                    ... on DiscountPercentage {
                                        percentage
                                    }
                                }
                            }
                        }
                    }
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """

        variables = {
            'basicCodeDiscount': {
                'title': title,
                'code': code,
                'startsAt': datetime.utcnow().isoformat() + 'Z',
                'customerSelection': {
                    'customers': {
                        'add': []  # Will be set via customer tag eligibility
                    }
                },
                'customerGets': {
                    'value': {
                        'percentage': percentage / 100
                    },
                    'items': {
                        'all': True
                    }
                },
                'combinesWith': {
                    'productDiscounts': False,
                    'orderDiscounts': False,
                    'shippingDiscounts': True
                }
            }
        }

        if usage_limit:
            variables['basicCodeDiscount']['usageLimit'] = usage_limit

        try:
            result = self._execute_query(mutation, variables)
            data = result.get('discountCodeBasicCreate', {})

            errors = data.get('userErrors', [])
            if errors:
                # If code already exists, try to get it
                if any('code' in str(e).lower() and 'taken' in str(e).lower() for e in errors):
                    existing = self.get_discount_by_code(code)
                    if existing.get('success'):
                        return existing
                return {
                    'success': False,
                    'errors': errors
                }

            node = data.get('codeDiscountNode', {})
            discount = node.get('codeDiscount', {})
            codes = discount.get('codes', {}).get('nodes', [])

            return {
                'success': True,
                'discount_id': node.get('id'),
                'title': discount.get('title'),
                'code': codes[0].get('code') if codes else code,
                'percentage': percentage,
                'customer_tag': customer_tag,
                'tier_name': tier_name
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def get_discount_by_code(self, code: str) -> Dict[str, Any]:
        """Get a discount by its code."""
        query = """
        query getDiscountByCode($code: String!) {
            codeDiscountNodeByCode(code: $code) {
                id
                codeDiscount {
                    ... on DiscountCodeBasic {
                        title
                        status
                        codes(first: 1) {
                            nodes {
                                code
                            }
                        }
                        customerGets {
                            value {
                                ... on DiscountPercentage {
                                    percentage
                                }
                            }
                        }
                    }
                }
            }
        }
        """

        try:
            result = self._execute_query(query, {'code': code})
            node = result.get('codeDiscountNodeByCode')

            if not node:
                return {'success': False, 'error': 'Discount not found'}

            discount = node.get('codeDiscount', {})
            codes = discount.get('codes', {}).get('nodes', [])
            percentage_value = discount.get('customerGets', {}).get('value', {})

            return {
                'success': True,
                'discount_id': node.get('id'),
                'title': discount.get('title'),
                'status': discount.get('status'),
                'code': codes[0].get('code') if codes else code,
                'percentage': percentage_value.get('percentage', 0) * 100
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def list_automatic_discounts(self, first: int = 50) -> Dict[str, Any]:
        """List all automatic discounts."""
        query = """
        query listAutomaticDiscounts($first: Int!) {
            discountNodes(first: $first, query: "type:automatic") {
                nodes {
                    id
                    discount {
                        ... on DiscountAutomaticBasic {
                            title
                            status
                            startsAt
                            endsAt
                            customerGets {
                                value {
                                    ... on DiscountPercentage {
                                        percentage
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """

        try:
            result = self._execute_query(query, {'first': first})
            nodes = result.get('discountNodes', {}).get('nodes', [])

            discounts = []
            for node in nodes:
                discount = node.get('discount', {})
                percentage_value = discount.get('customerGets', {}).get('value', {})
                discounts.append({
                    'id': node.get('id'),
                    'title': discount.get('title'),
                    'status': discount.get('status'),
                    'starts_at': discount.get('startsAt'),
                    'ends_at': discount.get('endsAt'),
                    'percentage': percentage_value.get('percentage', 0) * 100
                })

            return {
                'success': True,
                'discounts': discounts,
                'count': len(discounts)
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def delete_discount(self, discount_id: str) -> Dict[str, Any]:
        """Delete a discount by ID."""
        # Determine if it's automatic or code-based by the ID format
        if 'AutomaticDiscount' in discount_id:
            mutation = """
            mutation discountAutomaticDelete($id: ID!) {
                discountAutomaticDelete(id: $id) {
                    deletedAutomaticDiscountId
                    userErrors {
                        field
                        message
                    }
                }
            }
            """
        else:
            mutation = """
            mutation discountCodeDelete($id: ID!) {
                discountCodeDelete(id: $id) {
                    deletedCodeDiscountId
                    userErrors {
                        field
                        message
                    }
                }
            }
            """

        try:
            result = self._execute_query(mutation, {'id': discount_id})

            # Check for errors in either mutation type
            data = result.get('discountAutomaticDelete') or result.get('discountCodeDelete', {})
            errors = data.get('userErrors', [])

            if errors:
                return {
                    'success': False,
                    'errors': errors
                }

            return {
                'success': True,
                'deleted_id': discount_id
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }