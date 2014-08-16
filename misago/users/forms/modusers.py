from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils.translation import ugettext_lazy as _, ungettext
from django.utils import timezone

from misago.conf import settings
from misago.core import forms

from misago.users.forms.admin import BanUsersForm
from misago.users.models import Ban


class WarnUserForm(forms.Form):
    reason = forms.CharField(label=_("Warning Reason"),
                             help_text=_("Optional message explaining why "
                                         "this warning was given."),
                             widget=forms.Textarea(attrs={'rows': 8}),
                             required=False)

    def clean_reason(self):
        data = self.cleaned_data['reason']
        if len(data) > 2000:
            message = _("Warning reason can't be longer than 2000 characters.")
            raise forms.ValidationError(message)
        return data


class ModerateAvatarForm(forms.ModelForm):
    is_avatar_locked = forms.YesNoSwitch(
        label=_("Lock avatar"),
        help_text=_("Setting this to yes will stop user from "
                    "changing his/her avatar, and will reset "
                    "his/her avatar to procedurally generated one."))
    avatar_lock_user_message = forms.CharField(
        label=_("User message"),
        help_text=_("Optional message for user explaining "
                    "why he/she is banned form changing avatar."),
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False)
    avatar_lock_staff_message = forms.CharField(
        label=_("Staff message"),
        help_text=_("Optional message for forum team members explaining "
                    "why user is banned form changing avatar."),
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False)

    class Meta:
        model = get_user_model()
        fields = [
            'is_avatar_locked',
            'avatar_lock_user_message',
            'avatar_lock_staff_message',
        ]


class ModerateSignatureForm(forms.ModelForm):
    signature = forms.CharField(
        label=_("Signature contents"),
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False)
    is_signature_locked = forms.YesNoSwitch(
        label=_("Lock signature"),
        help_text=_("Setting this to yes will stop user from "
                    "making changes to his/her signature."))
    signature_lock_user_message = forms.CharField(
        label=_("User message"),
        help_text=_("Optional message to user explaining "
                    "why his/hers signature is locked."),
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False)
    signature_lock_staff_message = forms.CharField(
        label=_("Staff message"),
        help_text=_("Optional message to team members explaining "
                    "why user signature is locked."),
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False)

    class Meta:
        model = get_user_model()
        fields = [
            'signature',
            'is_signature_locked',
            'signature_lock_user_message',
            'signature_lock_staff_message'
        ]

    def clean_signature(self):
        data = self.cleaned_data['signature']

        length_limit = settings.signature_length_max
        if len(data) > length_limit:
            raise forms.ValidationError(ungettext(
                "Signature can't be longer than %(limit)s character.",
                "Signature can't be longer than %(limit)s characters.",
                length_limit) % {'limit': length_limit})

        return data


class BanForm(BanUsersForm):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')
        super(BanForm, self).__init__(*args, **kwargs)

        if self.user.acl_['max_ban_length']:
            message = ungettext(
                "Required. Can't be longer than %(days)s day.",
                "Required. Can't be longer than %(days)s days.",
                self.user.acl_['max_ban_length'])
            message = message % {'days': self.user.acl_['max_ban_length']}
            self['valid_until'].field.help_text = message

    def clean_valid_until(self):
        data = self.cleaned_data['valid_until']

        if self.user.acl_['max_ban_length']:
            max_ban_length = timedelta(days=self.user.acl_['max_ban_length'])
            if not data or data > (timezone.now() + max_ban_length).date():
                message = ungettext(
                    "You can't set bans longer than %(days)s day.",
                    "You can't set bans longer than %(days)s days.",
                    self.user.acl_['max_ban_length'])
                message = message % {'days': self.user.acl_['max_ban_length']}
                raise forms.ValidationError(message)
        elif data and data < timezone.now().date():
            raise forms.ValidationError(_("Expiration date is in past."))

        return data

    def ban_user(self):
        new_ban = Ban(banned_value=self.user.username,
                      user_message=self.cleaned_data['user_message'],
                      staff_message=self.cleaned_data['staff_message'],
                      valid_until=self.cleaned_data['valid_until'])
        new_ban.save()

        Ban.objects.invalidate_cache()
