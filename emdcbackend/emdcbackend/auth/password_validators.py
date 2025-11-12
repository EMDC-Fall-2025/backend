"""
Custom password validators for EMDC application.
"""
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class UppercasePasswordValidator:
    """
    Validate that the password contains at least one uppercase letter.
    """
    def validate(self, password, user=None):
        if not any(char.isupper() for char in password):
            raise ValidationError(
                _("The password must contain at least one uppercase letter."),
                code='password_no_uppercase',
            )

    def get_help_text(self):
        return _("Your password must contain at least one uppercase letter.")


class LowercasePasswordValidator:
    """
    Validate that the password contains at least one lowercase letter.
    """
    def validate(self, password, user=None):
        if not any(char.islower() for char in password):
            raise ValidationError(
                _("The password must contain at least one lowercase letter."),
                code='password_no_lowercase',
            )

    def get_help_text(self):
        return _("Your password must contain at least one lowercase letter.")


class SpecialCharacterPasswordValidator:
    """
    Validate that the password contains at least one special character.
    Special characters are: !@#$%^&*()_+-=[]{}|;:,.<>?
    """
    def validate(self, password, user=None):
        import string
        special_chars = set(string.punctuation)
        if not any(char in special_chars for char in password):
            raise ValidationError(
                _("The password must contain at least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)."),
                code='password_no_special',
            )

    def get_help_text(self):
        return _("Your password must contain at least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?).")

