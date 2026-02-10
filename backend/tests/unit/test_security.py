from app.services.data_access import SecurityValidator

# --- SQL INJECTION & SECURITY TESTS ---


class TestSecurityValidator:

    def test_safe_select_query(self):
        """Standard valid SELECT query should pass."""
        query = "SELECT * FROM products WHERE price < 100"
        assert SecurityValidator.is_safe_sql(query) is True

    def test_forbidden_keywords_drop(self):
        """DROP command must be rejected."""
        query = "SELECT * FROM products; DROP TABLE products;"
        assert SecurityValidator.is_safe_sql(query) is False

    def test_forbidden_keywords_delete(self):
        """DELETE command must be rejected."""
        query = "DELETE FROM products WHERE id = 1"
        assert SecurityValidator.is_safe_sql(query) is False

    def test_forbidden_keywords_insert(self):
        """INSERT command must be rejected."""
        query = "INSERT INTO products (name) VALUES ('Hacked')"
        assert SecurityValidator.is_safe_sql(query) is False

    def test_case_insensitivity(self):
        """Validator must handle mixed case injection attempts."""
        query = "SeLeCt * FrOm products; dRoP tAbLe products"
        assert SecurityValidator.is_safe_sql(query) is False

    def test_semicolon_chaining(self):
        """Semicolon chaining must be rejected even without keywords."""
        query = "SELECT * FROM products; SELECT * FROM secrets"
        assert SecurityValidator.is_safe_sql(query) is False

    def test_must_start_with_select(self):
        """Query must strictly start with SELECT."""
        query = "UPDATE products SET price = 0"
        assert SecurityValidator.is_safe_sql(query) is False

    def test_whitespace_padding(self):
        """Leading/Trailing whitespace should not bypass validation."""
        query = "   SELECT * FROM products   "
        assert SecurityValidator.is_safe_sql(query) is True
