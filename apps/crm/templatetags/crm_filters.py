from django import template

register = template.Library()


@register.filter
def sep_milliers(value):
    """Format a number with narrow no-break space as French thousand separator.

    Ex : 723669016 → '723 669 016'
    """
    try:
        v = float(value)
        formatted = f"{int(round(v)):,}".replace(",", " ")
        return formatted
    except (ValueError, TypeError):
        return value
