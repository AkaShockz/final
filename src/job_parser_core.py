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
        return self.jobs
    
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
        job['SPECIAL INSTRUCTIONS'] = 'Must call 1hour before collection and get a name'
        job['PRICE'] = ''
        job['CUSTOMER REF'] = 'AC01'
        job['TRANSPORT TYPE'] = ''
        from_match = re.search(r'FROM\n(.*?)(?=\nTO|$)', job_text, re.DOTALL)
        if from_match:
            from_text = from_match.group(1).strip()
            from_lines = [line.strip() for line in from_text.split('\n') if line.strip()]
            phone_lines = [line for line in from_lines if re.search(r'(?:Tel|Phone|T|Telephone)[\s:.]+[+\d()\s-]+', line, re.IGNORECASE)]
            if phone_lines:
                phone_match = re.search(r'(?:Tel|Phone|T|Telephone)[\s:.]+([+\d()\s-]+)', phone_lines[0], re.IGNORECASE)
                if phone_match:
                    job['COLLECTION PHONE'] = self.clean_phone_number(phone_match.group(1))
        # ... (rest of parse_single_job logic as in your original)
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