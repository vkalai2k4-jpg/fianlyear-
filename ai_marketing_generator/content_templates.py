# Marketing type templates.
# The campaign form dropdown is built automatically from these keys -
# add a new entry here and it shows up in the dropdown without touching app.py.
#
# Each template has a headline/caption/cta with {placeholders} that get filled
# in from the campaign's product_name, description, target_audience etc.
# Used when the owner picks "Use Template" instead of "Use AI".

TEMPLATES = {
    "Festival offer": {
        "headline": "Celebrate the festive season with {product_name}!",
        "caption": "{description} Special festive pricing available for a limited time - {audience_line}",
        "cta": "Claim festive offer",
    },
    "Product launch": {
        "headline": "Introducing {product_name}",
        "caption": "{description} Now available - {audience_line}",
        "cta": "Explore now",
    },
    "Discount sale": {
        "headline": "Big savings on {product_name}",
        "caption": "{description} Grab it before the offer ends - {audience_line}",
        "cta": "Shop the sale",
    },
    "Seasonal clearance": {
        "headline": "Season-end clearance: {product_name}",
        "caption": "{description} Limited stock at clearance prices - {audience_line}",
        "cta": "Shop clearance",
    },
    "New service announcement": {
        "headline": "We're now offering {product_name}",
        "caption": "{description} Designed for {audience_line}",
        "cta": "Learn more",
    },
    "Customer appreciation": {
        "headline": "A thank you from us to you",
        "caption": "{description} As a valued customer, enjoy something special on {product_name}.",
        "cta": "See your reward",
    },
    "Referral offer": {
        "headline": "Refer a friend, both of you save on {product_name}",
        "caption": "{description} Perfect for {audience_line} to share the benefit.",
        "cta": "Refer now",
    },
    "Event/webinar invite": {
        "headline": "You're invited: {product_name}",
        "caption": "{description} Reserve your spot today - {audience_line}",
        "cta": "Register now",
    },
    "Limited stock alert": {
        "headline": "Almost gone: {product_name}",
        "caption": "{description} Only a few left in stock - {audience_line}",
        "cta": "Order before it's gone",
    },
    "Weekend special": {
        "headline": "Weekend special on {product_name}",
        "caption": "{description} This weekend only - {audience_line}",
        "cta": "Grab the deal",
    },
    "Loyalty reward": {
        "headline": "A reward just for you",
        "caption": "{description} Thanks for sticking with us - here's something back on {product_name}.",
        "cta": "Redeem reward",
    },
    "Back-in-stock notice": {
        "headline": "{product_name} is back in stock",
        "caption": "{description} Restocked and ready to ship - {audience_line}",
        "cta": "Buy now",
    },
}


def get_marketing_type_choices():
    """Returns the list of marketing type names, used to build the dropdown."""
    return list(TEMPLATES.keys())


def fill_template(marketing_type, product_name, description, audience):
    """
    Fills the chosen template's placeholders with campaign details.
    Returns a dict: {headline, caption, cta}
    Falls back to the first template if an unknown marketing_type is passed in.
    """
    template = TEMPLATES.get(marketing_type) or next(iter(TEMPLATES.values()))
    audience_line = f"made for {audience}" if audience else "made for you"

    return {
        "headline": template["headline"].format(product_name=product_name),
        "caption": template["caption"].format(
            description=description, audience_line=audience_line, product_name=product_name
        ),
        "cta": template["cta"],
    }
