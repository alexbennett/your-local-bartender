#!/usr/bin/env python
#
# Copyright (C) 2020 Elexa Consumer Product, Inc.
#
# This file is part of the Guardian Cloud API.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import connexion

from ylb import config

options = {"swagger_ui": config.ENABLE_SWAGGER}

# Create the application instance
app = connexion.App(__name__, options=options)
app.add_api(config.openapi_yaml)
