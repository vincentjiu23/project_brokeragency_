# -*- coding: utf-8 -*-
from odoo import models, fields

class VinPartnerExpertise(models.Model):
    _name = 'vin.partner.expertise'
    _description = 'Creative Partner Skill & Expertise Tag'
    _order = 'name asc'

    name = fields.Char(
        string='Skill / Discipline Name',
        required=True,
        translate=True
    )
    code = fields.Char(
        string='Skill Code',
        required=True,
        index=True
    )
    category = fields.Selection(
        [
            ('visual_design', 'Visual & Graphic Design'),
            ('video_motion', 'Video Production & Motion Graphics'),
            ('3d_cgi', '3D Modeling, Animation & CGI'),
            ('copy_content', 'Copywriting & Content Strategy'),
            ('branding', 'Brand Strategy & Identity'),
            ('audio', 'Audio Engineering & Sound Design'),
            ('interactive', 'UI/UX & Interactive Design')
        ],
        string='Discipline Category',
        required=True,
        index=True
    )

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'The expertise skill code must be unique!')
    ]
