import re
from datetime import datetime, timedelta
import holidays

class JobParser:
    def __init__(self, collection_date, delivery_date=None):
        self.jobs = []
        self.collection_date = collection_date
        self.delivery_date = delivery_date if delivery_date else collection_date
        
    def calculate_delivery_date(self, collection_date):
        """Calculate delivery date as 3 business days from collection date."""
        if isinstance(collection_date, str):
            collection_date = datetime.strptime(collection_date, "%d/%m/%Y")
        uk_holidays = holidays.UK()
        current_date = collection_date
        business_days = 0
        while business_days < 3:
            current_date += timedelta(days=1)
            if current_date.weekday() < 5 and current_date not in uk_holidays:
                business_days += 1
        return current_date.strftime("%d/%m/%Y")
    
    def fix_location_name(self, name):
        name = name.replace('18 AC Stoke Logistics Hub', '18 Arnold Clark Stoke Logistics Hub')
        name = name.replace('4 AC Accrington Logistics Hub', '4 Arnold Clark Accrington Logistics Hub')
        if "Unit 1 Calder Park Services" in name:
            return "Wakefield Motorstore"
        if name.startswith("Unit ") and len(name.split()) >= 3:
            pass
        return name
    
    def clean_phone_number(self, phone):
        if not phone:
            return ""
        digits = ''.join(c for c in phone if c.isdigit())
        if digits.startswith('44'):
            digits = digits[2:]
        elif digits.startswith('0044'):
            digits = digits[4:]
        elif digits.startswith('0'):
            digits = digits[1:]
        if len(digits) > 10:
            digits = digits[:10]
        elif len(digits) < 10:
            digits = digits.ljust(10, '0')
        return digits

    def is_postcode(self, line):
        postcode_patterns = [
            r'^[A-Z]{1,2}[0-9][0-9A-Z]?\s*[0-9][A-Z]{2}$',
            r'^[A-Za-z]{1,2}[0-9][0-9A-Za-z]?\s*[0-9][A-Za-z]{2}$',
            r'^(?:Postcode|Post Code|P/Code|PC)[\s:]+[A-Za-z]{1,2}[0-9][0-9A-Za-z]?\s*[0-9][A-Za-z]{2}$'
        ]
        line = line.strip()
        for pattern in postcode_patterns:
            if re.match(pattern, line):
                postcode_match = re.search(r'([A-Za-z]{1,2}[0-9][0-9A-Za-z]?\s*[0-9][A-Za-z]{2})$', line)
                if postcode_match:
                    return postcode_match.group(1).upper()
        return None

    def parse_jobs(self, text):
        # First try the tabular format
        tabular_jobs = self.parse_tabular_format(text)
        if tabular_jobs:
            self.jobs.extend(tabular_jobs)
            return self.jobs
            
        # If tabular format didn't work, try the traditional format
        job_texts = re.split(r'\nFROM\n', text)
        job_texts = [t for t in job_texts if t.strip()]
        for job_text in job_texts:
            if not job_text.startswith('FROM'):
                job_text = 'FROM\n' + job_text
            if not re.search(r'TO\n', job_text):
                continue
            job = self.parse_single_job(job_text)
            if job:
                if 'SPECIAL INSTRUCTIONS' not in job or not job['SPECIAL INSTRUCTIONS']:
                    job['SPECIAL INSTRUCTIONS'] = 'Please call 1 hour before collection'
                self.jobs.append(job)
                
        # If no jobs were found using either method, try a simple line-by-line approach
        if not self.jobs:
            lines = text.strip().split('\n')
            for line in lines:
                if re.search(r'[A-Z]{2}\d{2}\s*[A-Z]{3}', line):
                    job = self.create_empty_job()
                    reg_match = re.search(r'([A-Z]{2}\d{2}\s*[A-Z]{3})', line)
                    if reg_match:
                        job['REG NUMBER'] = reg_match.group(1).replace(' ', '')
                        self.jobs.append(job)
                        
        return self.jobs
    
    def parse_tabular_format(self, text):
        """Parse a tabular format where each row is a job and columns are fields."""
        jobs = []
        lines = text.strip().split('\n')
        lines = [line.strip() for line in lines if line.strip()]
        
        # Find the header row
        header_row = None
        for i, line in enumerate(lines):
            if re.search(r'REG\s*(?:NUMBER|NO)', line, re.IGNORECASE):
                header_row = i
                break
        
        if header_row is None:
            return []
        
        # Process data rows
        for i in range(header_row + 1, len(lines)):
            line = lines[i].strip()
            if not line or line.lower().startswith('reg') or len(line) < 10:
                continue
                
            # Check if this line contains a registration number
            reg_match = re.search(r'([A-Z]{2}\d{2}\s*[A-Z]{3})', line)
            if reg_match:
                job = self.create_empty_job()
                job['REG NUMBER'] = reg_match.group(1).replace(' ', '')
                
                # Try to extract other information from the line
                # VIN (usually follows registration number)
                vin_match = re.search(r'[A-Z]{2}\d{2}\s*[A-Z]{3}\s+([A-Z0-9]{17})', line)
                if vin_match:
                    job['VIN'] = vin_match.group(1)
                
                # Make/Model (often follows VIN or registration)
                make_model_match = re.search(r'[A-Z0-9]{17}\s+([A-Za-z]+)\s+([A-Za-z0-9\s]+)', line)
                if make_model_match:
                    job['MAKE'] = make_model_match.group(1)
                    job['MODEL'] = make_model_match.group(2).strip()
                
                # Color (might be after make/model)
                color_match = re.search(r'(?:' + re.escape(job['MODEL']) + r')\s+([A-Za-z]+)', line) if job['MODEL'] else None
                if color_match:
                    job['COLOR'] = color_match.group(1)
                
                # Look for collection and delivery addresses in nearby lines
                if i > 0 and i < len(lines) - 1:
                    # Check previous line for collection address
                    if 'COLLECTION ADDR1' not in job or not job['COLLECTION ADDR1']:
                        coll_addr = lines[i-1].strip()
                        if coll_addr and not re.search(r'REG|NUMBER|MAKE|MODEL', coll_addr, re.IGNORECASE):
                            job['COLLECTION ADDR1'] = coll_addr
                    
                    # Check next line for delivery address
                    if 'DELIVERY ADDR1' not in job or not job['DELIVERY ADDR1']:
                        del_addr = lines[i+1].strip()
                        if del_addr and not re.search(r'REG|NUMBER|MAKE|MODEL', del_addr, re.IGNORECASE):
                            job['DELIVERY ADDR1'] = del_addr
                
                jobs.append(job)
        
        return jobs
    
    def create_empty_job(self):
        """Create an empty job dictionary with default values."""
        return {
            'REG NUMBER': '',
            'VIN': '',
            'MAKE': '',
            'MODEL': '',
            'COLOR': '',
            'COLLECTION DATE': self.collection_date,
            'YOUR REF NO': '',
            'COLLECTION ADDR1': '',
            'COLLECTION ADDR2': '',
            'COLLECTION ADDR3': '',
            'COLLECTION ADDR4': '',
            'COLLECTION POSTCODE': '',
            'COLLECTION CONTACT NAME': '',
            'COLLECTION PHONE': '',
            'DELIVERY DATE': self.delivery_date,
            'DELIVERY ADDR1': '',
            'DELIVERY ADDR2': '',
            'DELIVERY ADDR3': '',
            'DELIVERY ADDR4': '',
            'DELIVERY POSTCODE': '',
            'DELIVERY CONTACT NAME': '',
            'DELIVERY CONTACT PHONE': '',
            'SPECIAL INSTRUCTIONS': 'Please call 1 hour before collection',
            'PRICE': '',
            'CUSTOMER REF': 'AC01',
            'TRANSPORT TYPE': ''
        }
    
    def parse_address_lines(self, lines):
        preserved_patterns = [
            (r'St\.\s+[A-Z][a-z]+', lambda m: m.group().replace('.', '@')),
            (r'St\s+[A-Z][a-z]+', lambda m: m.group().replace(' ', '#')),
            (r'D\.\s*M\.\s*Keith', lambda m: m.group().replace('.', '@')),
            (r'[A-Z]\.\s+[A-Z]\.\s+\w+', lambda m: m.group().replace('.', '@')),
        ]
        processed_lines = []
        for line in lines:
            if not line.strip():
                continue
            processed_line = line
            for pattern, replacement in preserved_patterns:
                processed_line = re.sub(pattern, replacement, processed_line)
            processed_line = processed_line.replace('@', '.').replace('#', ' ')
            processed_lines.append(processed_line.strip())
        return processed_lines

    def clean_duplicate_towns(self, lines):
        if not lines:
            return lines
        cleaned_lines = []
        i = 0
        while i < len(lines):
            if i == len(lines) - 1 or lines[i].strip().upper() != lines[i + 1].strip().upper():
                cleaned_lines.append(lines[i])
                i += 1
            else:
                i += 1
        return cleaned_lines

    def parse_single_job(self, job_text):
        job = self.create_empty_job()
        
        # Extract FROM section
        from_match = re.search(r'FROM\n(.*?)(?=\nTO\n|$)', job_text, re.DOTALL)
        if from_match:
            from_text = from_match.group(1).strip()
            from_lines = [line.strip() for line in from_text.split('\n') if line.strip()]
            
            # Extract collection phone
            phone_lines = [line for line in from_lines if re.search(r'(?:Tel|Phone|T|Telephone)[\s:.]+[+\d()\s-]+', line, re.IGNORECASE)]
            if phone_lines:
                phone_match = re.search(r'(?:Tel|Phone|T|Telephone)[\s:.]+([+\d()\s-]+)', phone_lines[0], re.IGNORECASE)
                if phone_match:
                    job['COLLECTION PHONE'] = self.clean_phone_number(phone_match.group(1))
            
            # Extract collection address
            address_lines = []
            for line in from_lines:
                if not re.search(r'(?:Tel|Phone|T|Telephone)', line, re.IGNORECASE) and line.strip():
                    address_lines.append(line.strip())
            
            address_lines = self.parse_address_lines(address_lines)
            address_lines = self.clean_duplicate_towns(address_lines)
            
            # Find postcode
            postcode_idx = -1
            for i, line in enumerate(address_lines):
                if self.is_postcode(line):
                    postcode_idx = i
                    job['COLLECTION POSTCODE'] = self.is_postcode(line)
                    break
            
            # Assign address components
            if postcode_idx >= 0:
                addr_parts = address_lines[:postcode_idx]
            else:
                addr_parts = address_lines
            
            # Clean up address parts
            addr_parts = [p for p in addr_parts if p.strip()]
            
            # Assign address fields
            if addr_parts:
                for i, part in enumerate(addr_parts):
                    if i < 4:
                        job[f'COLLECTION ADDR{i+1}'] = part
        
        # Extract TO section
        to_match = re.search(r'TO\n(.*?)(?=\nVEHICLE|$)', job_text, re.DOTALL)
        if to_match:
            to_text = to_match.group(1).strip()
            to_lines = [line.strip() for line in to_text.split('\n') if line.strip()]
            
            # Extract delivery phone
            phone_lines = [line for line in to_lines if re.search(r'(?:Tel|Phone|T|Telephone)[\s:.]+[+\d()\s-]+', line, re.IGNORECASE)]
            if phone_lines:
                phone_match = re.search(r'(?:Tel|Phone|T|Telephone)[\s:.]+([+\d()\s-]+)', phone_lines[0], re.IGNORECASE)
                if phone_match:
                    job['DELIVERY CONTACT PHONE'] = self.clean_phone_number(phone_match.group(1))
            
            # Extract delivery address
            address_lines = []
            for line in to_lines:
                if not re.search(r'(?:Tel|Phone|T|Telephone)', line, re.IGNORECASE) and line.strip():
                    address_lines.append(line.strip())
            
            address_lines = self.parse_address_lines(address_lines)
            address_lines = self.clean_duplicate_towns(address_lines)
            
            # Find postcode
            postcode_idx = -1
            for i, line in enumerate(address_lines):
                if self.is_postcode(line):
                    postcode_idx = i
                    job['DELIVERY POSTCODE'] = self.is_postcode(line)
                    break
            
            # Assign address components
            if postcode_idx >= 0:
                addr_parts = address_lines[:postcode_idx]
            else:
                addr_parts = address_lines
            
            # Clean up address parts
            addr_parts = [p for p in addr_parts if p.strip()]
            
            # Assign address fields
            if addr_parts:
                for i, part in enumerate(addr_parts):
                    if i < 4:
                        job[f'DELIVERY ADDR{i+1}'] = part
        
        # Extract vehicle details
        vehicle_match = re.search(r'VEHICLE\n(.*?)(?=\nSPECIAL|$)', job_text, re.DOTALL)
        if vehicle_match:
            vehicle_text = vehicle_match.group(1).strip()
            vehicle_lines = [line.strip() for line in vehicle_text.split('\n') if line.strip()]
            
            # Extract registration number
            reg_pattern = r'([A-Z]{2}\d{2}\s*[A-Z]{3})'
            for line in vehicle_lines:
                reg_match = re.search(reg_pattern, line)
                if reg_match:
                    job['REG NUMBER'] = reg_match.group(1).replace(' ', '')
                    break
            
            # Extract VIN
            vin_pattern = r'(?:VIN|CHASSIS)[\s:.]+([A-Z0-9]{17})'
            for line in vehicle_lines:
                vin_match = re.search(vin_pattern, line, re.IGNORECASE)
                if vin_match:
                    job['VIN'] = vin_match.group(1)
                    break
            
            # Extract make and model
            make_model_pattern = r'(?:MAKE/MODEL|MAKE & MODEL)[\s:.]+(.+)'
            for line in vehicle_lines:
                make_model_match = re.search(make_model_pattern, line, re.IGNORECASE)
                if make_model_match:
                    make_model = make_model_match.group(1).strip()
                    parts = make_model.split(' ', 1)
                    if len(parts) >= 2:
                        job['MAKE'] = parts[0].strip()
                        job['MODEL'] = parts[1].strip()
                    elif len(parts) == 1:
                        job['MAKE'] = parts[0].strip()
                    break
        
        # Extract special instructions
        special_match = re.search(r'SPECIAL INSTRUCTIONS\n(.*?)(?=\n\n|$)', job_text, re.DOTALL)
        if special_match:
            special_text = special_match.group(1).strip()
            if special_text:
                job['SPECIAL INSTRUCTIONS'] = special_text
        
        return job

class BC04Parser:
    def __init__(self, collection_date, delivery_date=None):
        self.jobs = []
        self.collection_date = collection_date
        self.delivery_date = delivery_date if delivery_date else collection_date
        self.bc04_special_instructions = (
            "MUST GET A FULL NAME AND SIGNATURE ON COLLECTION CALL OFFICE AND Non Conformance Motability on 0121 788 6940 option 1 IF THEY REFUSE ** - PHOTO'S MUST BE CLEAR PLEASE. COLL AND DEL 09:00-17:00 ONLY"
        )
    def calculate_delivery_date(self, collection_date):
        try:
            import holidays
            uk_holidays = holidays.UnitedKingdom()
        except ImportError:
            class DummyHolidays:
                def __init__(self, *args, **kwargs):
                    pass
                def __contains__(self, date):
                    return False
            uk_holidays = DummyHolidays()
        delivery = collection_date
        delivery += timedelta(days=1)
        while delivery.weekday() >= 5 or delivery in uk_holidays:
            delivery += timedelta(days=1)
        return delivery
    def clean_phone_number(self, phone):
        if not phone:
            return ''
        phone = phone.strip()
        phone = re.sub(r'^(Tel|Phone|T|Telephone)[\s:.]*', '', phone, flags=re.IGNORECASE)
        phone = re.sub(r'[^\d+\s()-]', '', phone)
        phone = re.sub(r'\s+', ' ', phone).strip()
        return phone
    def is_postcode(self, line):
        postcode_pattern = r'\b([A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2})\b'
        match = re.search(postcode_pattern, line.upper())
        if match:
            postcode = match.group(1)
            postcode = re.sub(r'([A-Z]\d+[A-Z]?)(\d[A-Z]{2})', r'\1 \2', postcode)
            return postcode
        return None
    def parse_jobs(self, text):
        self.jobs = []
        job_sections = re.split(r'Job Sheet\s*\n', text)
        job_sections = [section.strip() for section in job_sections if section.strip()]
        for section in job_sections:
            if section.strip():
                job = self.parse_single_job(section)
                if job and job.get('REG NUMBER'):
                    self.jobs.append(job)
        return self.jobs
    def parse_single_job(self, job_text):
        job = {}
        job['REG NUMBER'] = ''
        job['VIN'] = ''
        job['MAKE'] = ''
        job['MODEL'] = ''
        job['COLOR'] = ''
        job['COLLECTION DATE'] = self.collection_date
        job['YOUR REF NO'] = ''
        job['COLLECTION ADDR1'] = ''
        job['COLLECTION ADDR2'] = ''
        job['COLLECTION ADDR3'] = ''
        job['COLLECTION ADDR4'] = ''
        job['COLLECTION POSTCODE'] = ''
        job['COLLECTION CONTACT NAME'] = ''
        job['COLLECTION PHONE'] = ''
        job['DELIVERY DATE'] = self.delivery_date
        job['DELIVERY ADDR1'] = ''
        job['DELIVERY ADDR2'] = ''
        job['DELIVERY ADDR3'] = ''
        job['DELIVERY ADDR4'] = ''
        job['DELIVERY POSTCODE'] = ''
        job['DELIVERY CONTACT NAME'] = ''
        job['DELIVERY CONTACT PHONE'] = ''
        job['SPECIAL INSTRUCTIONS'] = self.bc04_special_instructions
        job['PRICE'] = ''
        job['CUSTOMER REF'] = 'BC04'
        job['TRANSPORT TYPE'] = ''
        job_number_match = re.search(r'Job Number.*?(\d+/\d+)', job_text, re.DOTALL)
        if job_number_match:
            job['YOUR REF NO'] = job_number_match.group(1)
        reg_match = re.search(r'([A-Z]{2}\d{2}[A-Z]{3})', job_text)
        if reg_match:
            job['REG NUMBER'] = reg_match.group(1)
        vin_match = re.search(rf'{job["REG NUMBER"]}\s+(\d{{9,}})', job_text) if job['REG NUMBER'] else None
        if vin_match:
            job['VIN'] = vin_match.group(1)
        job['MAKE'] = ''
        job['MODEL'] = ''
        price_matches = re.findall(r'£?\s*(\d+\.\d{2})', job_text)
        if len(price_matches) >= 2:
            job['PRICE'] = price_matches[1]
        elif price_matches:
            job['PRICE'] = price_matches[0]
        lines = [line.strip() for line in job_text.split('\n')]
        addr_start = None
        reg_line_idx = None
        reg_pattern = r'^[A-Z]{2}\d{2}[A-Z]{3}\s+\d{9,}'
        for i, line in enumerate(lines):
            if line.strip().lower().startswith('special instructions'):
                addr_start = i + 1
            if re.match(reg_pattern, line.strip()):
                reg_line_idx = i
                break
        if addr_start is not None and reg_line_idx is not None and addr_start < reg_line_idx:
            address_lines = [l for l in lines[addr_start:reg_line_idx] if l.strip()]
            postcode_indices = [i for i, l in enumerate(address_lines) if self.is_postcode(l)]
            if len(postcode_indices) == 2:
                split_idx = postcode_indices[0] + 1
            else:
                split_idx = len(address_lines) // 2
            collection_lines = address_lines[:split_idx]
            delivery_lines = address_lines[split_idx:]
            if collection_lines:
                c_postcode_idx = None
                for idx, l in enumerate(collection_lines):
                    if self.is_postcode(l):
                        c_postcode_idx = idx
                        break
                if c_postcode_idx is not None and c_postcode_idx > 0:
                    c_addr = collection_lines[:c_postcode_idx]
                    c_town = c_addr[-1] if len(c_addr) >= 1 else ''
                    for i in range(3):
                        job[f'COLLECTION ADDR{i+1}'] = c_addr[i] if i < len(c_addr)-1 else ''
                    job['COLLECTION ADDR4'] = c_town
                    job['COLLECTION POSTCODE'] = collection_lines[c_postcode_idx]
                else:
                    for idx, val in enumerate(collection_lines):
                        if idx < 4:
                            job[f'COLLECTION ADDR{idx+1}'] = val
            if delivery_lines:
                d_postcode_idx = None
                for idx, l in enumerate(delivery_lines):
                    if self.is_postcode(l):
                        d_postcode_idx = idx
                        break
                if d_postcode_idx is not None and d_postcode_idx > 0:
                    d_addr = delivery_lines[:d_postcode_idx]
                    d_town = d_addr[-1] if len(d_addr) >= 1 else ''
                    for i in range(3):
                        job[f'DELIVERY ADDR{i+1}'] = d_addr[i] if i < len(d_addr)-1 else ''
                    job['DELIVERY ADDR4'] = d_town
                    job['DELIVERY POSTCODE'] = delivery_lines[d_postcode_idx]
                else:
                    for idx, val in enumerate(delivery_lines):
                        if idx < 4:
                            job[f'DELIVERY ADDR{idx+1}'] = val
        phone_line = ''
        found_dates = False
        for i, line in enumerate(lines):
            phones = re.findall(r'\d{8,}', line)
            if len(phones) >= 2:
                if i+1 < len(lines) and re.match(r'\d{2}/\d{2}/\d{4}', lines[i+1]):
                    job['COLLECTION PHONE'] = phones[0]
                    job['DELIVERY CONTACT PHONE'] = phones[1]
                    date_matches = []
                    for l in lines[i+1:i+5]:
                        date_matches += re.findall(r'\d{2}/\d{2}/\d{4}', l)
                        if len(date_matches) >= 2:
                            break
        return job 