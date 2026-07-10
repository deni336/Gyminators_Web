from django.db import migrations


def seed_editable_content(apps, schema_editor):
    SiteConfiguration = apps.get_model("website", "SiteConfiguration")
    Program = apps.get_model("website", "Program")
    Event = apps.get_model("website", "Event")
    HomepageFeature = apps.get_model("website", "HomepageFeature")
    SocialLink = apps.get_model("website", "SocialLink")

    SiteConfiguration.objects.get_or_create(pk=1)

    programs = (
        {
            "name": "Parent & Tot",
            "slug": "parent-and-tot",
            "age_range": "Walking – age 3",
            "description": "A playful first introduction to movement, balance, and the gym with a parent or caregiver close by.",
            "image_alt": "Parent helping a young child practice gymnastics",
            "fallback_image": "images/5.jpg",
            "call_to_action_label": "Register for Parent & Tot",
            "featured": True,
            "display_order": 10,
        },
        {
            "name": "Preschool Gymnastics",
            "slug": "preschool-gymnastics",
            "age_range": "Ages 2½ – 5",
            "description": "Age-appropriate gymnastics that builds coordination, listening skills, confidence, and a love of movement.",
            "image_alt": "Preschool gymnast practicing foundational movement",
            "fallback_image": "images/1.jpg",
            "call_to_action_label": "Register for Preschool Gymnastics",
            "featured": True,
            "display_order": 20,
        },
        {
            "name": "Recreational Gymnastics",
            "slug": "recreational-gymnastics",
            "age_range": "Ages 5 – 17",
            "description": "Progressive instruction for beginners through advanced athletes in a positive, skill-focused environment.",
            "image_alt": "Gymnast practicing a recreational gymnastics skill",
            "fallback_image": "images/4.jpg",
            "call_to_action_label": "Register for Recreational Gymnastics",
            "featured": True,
            "display_order": 30,
        },
        {
            "name": "Competitive Team",
            "slug": "competitive-team",
            "age_range": "By placement or tryout",
            "description": "Focused coaching and team development for gymnasts ready to train, compete, and grow together.",
            "image_alt": "Competitive gymnast training in the gym",
            "fallback_image": "images/7.jpg",
            "call_to_action_label": "Ask about Competitive Team",
            "featured": True,
            "display_order": 40,
        },
        {"name": "Pre-Team / Hot Shots", "slug": "pre-team-hot-shots", "image_alt": "Gymnast in the Pre-Team program", "display_order": 50},
        {"name": "Tumbling", "slug": "tumbling", "image_alt": "Athlete practicing tumbling", "display_order": 60},
        {"name": "Hip-Hop Dance", "slug": "hip-hop-dance", "image_alt": "Students in hip-hop dance", "display_order": 70},
        {"name": "Boys Gymnastics", "slug": "boys-gymnastics", "image_alt": "Athlete in boys gymnastics", "display_order": 80},
        {"name": "Ninja Warriors", "slug": "ninja-warriors", "image_alt": "Child in the Ninja Warriors program", "display_order": 90},
        {"name": "Fit, Flex, Fun", "slug": "fit-flex-fun", "image_alt": "Children enjoying the Fit, Flex, Fun program", "display_order": 100},
    )
    for values in programs:
        defaults = {
            "age_range": "",
            "description": "Call the office to learn about current class times, placement, and availability.",
            "image_alt": values["image_alt"],
            "fallback_image": "",
            "call_to_action_url": "",
            "call_to_action_label": "Register",
            "featured": False,
            "published": True,
            "display_order": values["display_order"],
        }
        defaults.update({key: value for key, value in values.items() if key not in {"name", "slug"}})
        Program.objects.get_or_create(slug=values["slug"], defaults={"name": values["name"], **defaults})

    events = (
        {
            "title": "Open Gym",
            "slug": "open-gym",
            "description": "Extra time to move, practice, and have fun in the gym. Call for the current schedule and eligibility.",
            "schedule_text": "Call for current dates and times",
            "call_to_action_label": "Ask about Open Gym",
            "display_order": 10,
        },
        {
            "title": "Summer Camp",
            "slug": "summer-camp",
            "description": "Active camp days filled with gymnastics, games, challenges, and new friends.",
            "schedule_text": "Seasonal availability",
            "call_to_action_label": "Ask about Summer Camp",
            "display_order": 20,
        },
        {
            "title": "Birthday Parties",
            "slug": "birthday-parties",
            "description": "Celebrate with supervised gym fun and an experience built for energetic kids.",
            "schedule_text": "Advance reservation required",
            "call_to_action_label": "Plan a party",
            "display_order": 30,
        },
    )
    for values in events:
        Event.objects.get_or_create(slug=values["slug"], defaults=values)

    features = (
        ("proof", "Since 2003", "Serving Jacksonville families", 10),
        ("proof", "Walking – 17", "Programs for growing athletes", 20),
        ("proof", "Fully air-conditioned", "Comfortable year-round training", 30),
        ("benefit", "Confidence", "Progress that children can feel", 10),
        ("benefit", "Resilience", "Patient practice and brave attempts", 20),
        ("benefit", "Belonging", "A positive place to learn together", 30),
    )
    for section, title, body, display_order in features:
        HomepageFeature.objects.get_or_create(
            section=section,
            title=title,
            defaults={"body": body, "published": True, "display_order": display_order},
        )

    social_links = (
        ("Facebook", "https://www.facebook.com/GyminatorsGymnastics", 10),
        ("YouTube", "https://www.youtube.com/channel/UCNA-8EqPrPqJF_XSPu99CLw", 20),
        ("Instagram", "https://www.instagram.com/gyminatorsgymnastics/", 30),
    )
    for label, url, display_order in social_links:
        SocialLink.objects.get_or_create(
            label=label,
            defaults={"url": url, "published": True, "display_order": display_order},
        )


class Migration(migrations.Migration):
    dependencies = [("website", "0002_cms_management")]

    operations = [migrations.RunPython(seed_editable_content, migrations.RunPython.noop)]
