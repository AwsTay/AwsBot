#!/usr/bin/python
# -*- coding: utf-8 -*-

import pywikibot
from pywikibot import pagegenerators
import re
import sys
import random

class AwsBot:
    def __init__(self):
        self.site_ar = pywikibot.Site('ar', 'wikipedia')
        self.site_en = pywikibot.Site('en', 'wikipedia')
        
        self.MAX_SEE_ALSO_LINKS = 4
        
        self.re_see_also = re.compile(r'==\s*(?:انظر|أنظر|إطلع|طالع|شاهد|راجع|اقرأ|مقالات|مواضيع|صفحات|وصلات)\s*(?:أيضًا|أيضاً|ايضا|ايضاً|أيضا|ذات\s*صلة|متعلقة|مكملة|أخرى|اضافية|إضافية)?\s*==', re.IGNORECASE)
        
        self.re_link = re.compile(r'\[\[(.*?)(?:\|.*?)?\]\]')

        self.anchors = [
            re.compile(r'==\s*(?:(?:ال)?مراجع|ثبت المراجع|قائمة المراجع|الهوامش|المصادر والمراجع)\s*==', re.IGNORECASE),
            re.compile(r'\{\{(?:Reflist|مراجع|ثبت_المراجع|قائمة مراجع|لائحة مراجع).*?\}\}|<references\s*.*?>', re.IGNORECASE),
            re.compile(r'==\s*(?:ال)?مصادر\s*==', re.IGNORECASE),
            re.compile(r'==\s*(?:وصلات|روابط|مواقع|مصادر)\s*(?:خارجية|إضافية|اضافية|مختارة|الخارجية)\s*==', re.IGNORECASE)
        ]

    def is_date_or_year(self, title):
        if re.match(r'^(\d{3,4}|القرن .+|عقد \d{4})$', title): return True
        months = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", 
                  "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
                  "كانون", "شباط", "آذار", "نيسان", "أيار", "حزيران", 
                  "تموز", "آب", "أيلول", "تشرين"]
        if title in months: return True
        if any(m in title for m in months) and re.search(r'\d', title): return True
        return False

    def get_english_candidates(self, page):
        try:
            item = pywikibot.ItemPage.fromPage(page)
            if not item.exists() or 'enwiki' not in item.sitelinks: return []
            en_title = item.sitelinks['enwiki'].title
            en_page = pywikibot.Page(self.site_en, en_title)
            
            match = re.search(r'==\s*See\s+also\s*==', en_page.text, re.IGNORECASE)
            if not match: return []
            
            start = match.end()
            rest = en_page.text[start:]
            next_heading = re.search(r'==\s*.*?\s*==', rest)
            content = rest[:next_heading.start()] if next_heading else rest
            
            return self.re_link.findall(content)
        except:
            return []

    def task_see_also(self, page):
        text = page.text
        match_section = self.re_see_also.search(text)
        
        existing_links = []
        section_end_pos = 0
        has_section = False

        if match_section:
            has_section = True
            start_content = match_section.end()
            rest_text = text[start_content:]
            next_heading = re.search(r'==\s*.*?\s*==', rest_text)
            
            if next_heading:
                content_len = next_heading.start()
                section_content = rest_text[:content_len]
                section_end_pos = start_content + content_len
            else:
                section_content = rest_text
                section_end_pos = len(text)
            
            existing_links = self.re_link.findall(section_content)

        current_count = len(existing_links)
        if current_count >= 3: return None
        
        needed = self.MAX_SEE_ALSO_LINKS - current_count
        raw_candidates = self.get_english_candidates(page)
        
        if not raw_candidates: return None

        valid_candidates = []
        for link in raw_candidates:
            if len(valid_candidates) >= needed: break
            try:
                en_lnk = pywikibot.Page(self.site_en, link)
                if en_lnk.isRedirectPage(): en_lnk = en_lnk.getRedirectTarget()
                
                item = pywikibot.ItemPage.fromPage(en_lnk)
                if not item.exists() or 'arwiki' not in item.sitelinks: continue
                
                ar_title = item.sitelinks['arwiki'].title
                
                if ar_title in existing_links: continue
                if ar_title in text: continue
                if self.is_date_or_year(ar_title): continue
                
                ar_page = pywikibot.Page(self.site_ar, ar_title)
                if not ar_page.exists() or ar_page.isDisambig(): continue
                
                valid_candidates.append(ar_title)
            except: continue

        if not valid_candidates: return None

        valid_candidates.sort(key=len)
        bullets = "\n".join([f"* [[{l}]]" for l in valid_candidates])

        if has_section:
            new_text = text[:section_end_pos] + "\n" + bullets + text[section_end_pos:]
            page.text = new_text
            return f"بوت: إضافة {len(valid_candidates)} روابط لقسم انظر أيضًا (تكملة)"
        else:
            new_section_content = f"\n== انظر أيضًا ==\n{bullets}\n"
            
            possible_indices = []
            
            for regex in self.anchors:
                match = regex.search(text)
                if match:
                    possible_indices.append(match.start())
            
            is_last_section = False
            
            if possible_indices:
                insert_pos = min(possible_indices)
            else:
                insert_pos = len(text)
                is_last_section = True

            if is_last_section:
                ref_section = "\n== المراجع ==\n{{مراجع}}\n"
                new_section_content = f"{new_section_content}{ref_section}"
                summary_text = f"بوت: إضافة قسم انظر أيضًا ({len(valid_candidates)} مقترحة) وتجهيز قسم المراجع"
            else:
                summary_text = f"بوت: إضافة قسم انظر أيضًا ({len(valid_candidates)} مقالات مقترحة)"
                
            new_text = text[:insert_pos] + new_section_content + text[insert_pos:]
            
            page.text = new_text
            return summary_text

    def treat_page(self, page):
        pywikibot.output(f"\nChecking: {page.title(as_link=True)}...")
        if page.isRedirectPage() or page.isDisambig(): return

        summary = self.task_see_also(page)
        if summary:
            try:
                page.save(summary=summary)
                pywikibot.output(">> Saved successfully.")
            except Exception as e:
                pywikibot.output(f">> Error saving: {e}")

    def run(self, *args):
        local_args = pywikibot.handle_args(args)
        gen_factory = pagegenerators.GeneratorFactory()
        for arg in local_args:
            gen_factory.handle_arg(arg)
        generator = gen_factory.getCombinedGenerator()
        if generator:
            for page in generator:
                self.treat_page(page)
        else:
            pywikibot.output("Please specify a generator")

if __name__ == "__main__":
    if len(sys.argv) == 1:
        # هنا التغيير الجذري: إضافة -ns:0 لكل الأوضاع
        modes = [
            ['-random', '-ns:0'],
            ['-newpages', '-ns:0'],
            ['-cat:بذرة', '-ns:0']
        ]
        selected = random.choice(modes)
        sys.argv.extend(selected)
        pywikibot.output(f">> Auto-selected mode: {selected[0]} (Articles Only)")
        
    bot = AwsBot()
    bot.run()
