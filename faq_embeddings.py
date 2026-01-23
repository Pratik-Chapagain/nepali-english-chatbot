# faq_embeddings.py (FREE OFFLINE VERSION)
from sentence_transformers import SentenceTransformer
import json

# Your FAQ data (copy ALL your FAQs here)
FAQ_DATABASE = {
    "what is kancha ai": {
        "en": "Kancha AI is a bilingual AI assistant designed specifically for Nepali users. I can help with questions in English, Devanagari (नेपाली), or Romanized Nepali (Nepglish). I understand Nepal's culture, education system, and daily life.",
        "ne": "Kancha AI एक bilingual AI assistant हो जुन विशेष गरी नेपाली प्रयोगकर्ताहरूको लागि design गरिएको छ। म अंग्रेजी, देवनागरी (नेपाली), वा Romanized Nepali (Nepglish) मा प्रश्नहरूको उत्तर दिन सक्छु।",
        "np": "Kancha AI Nepal ko lagi banayeko bilingual AI assistant ho. Ma English, Devanagari (नेपाली), ya Romanized Nepali (Nepglish) ma help garna sakchu."
    },
    "who made you": {
        "en": "I was created to serve the Nepali community with culturally-aware AI assistance. I'm built using Google's Gemini AI with a custom system designed for Nepali users.",
        "ne": "म नेपाली समुदायलाई culturally-aware AI assistance प्रदान गर्न बनाइएको हुँ। म Google को Gemini AI प्रयोग गरेर नेपाली प्रयोगकर्ताहरूको लागि विशेष design गरिएको छु।",
        "np": "Ma Nepali community lai help garna banayeko chu. Google ko Gemini AI use garera Nepali users ko lagi special design gareko chu."
    },
    "what can you do": {
        "en": "I can help with:\n• General questions in English/Nepali\n• Nepal-related information (education, culture, daily life)\n• Study tips and career guidance\n• Language translation\n• Summarizing text\n• Cultural explanations",
        "ne": "म यी कुरामा मद्दत गर्न सक्छु:\n• English/Nepali मा सामान्य प्रश्नहरू\n• Nepal-related जानकारी (शिक्षा, संस्कृति, दैनिक जीवन)\n• अध्ययन tips र करियर guidance\n• भाषा अनुवाद\n• Text summarize गर्न\n• सांस्कृतिक व्याख्या",
        "np": "Ma yi kura ma help garna sakchu:\n• English/Nepali ma general questions\n• Nepal-related info (education, culture, daily life)\n• Study tips ra career guidance\n• Language translation\n• Text summarize garna\n• Cultural explanations"
    },
    "see exam": {
        "en": "SEE (Secondary Education Examination) is Nepal's grade 10 board exam conducted by the National Examinations Board (NEB). It's a crucial exam that determines eligibility for higher secondary education (+2).",
        "ne": "SEE (Secondary Education Examination) नेपालको कक्षा १० को board exam हो जुन राष्ट्रिय परीक्षा बोर्ड (NEB) द्वारा सञ्चालन गरिन्छ। यो उच्च माध्यमिक शिक्षा (+2) को लागि योग्यता निर्धारण गर्ने महत्त्वपूर्ण परीक्षा हो।",
        "np": "SEE (Secondary Education Examination) Nepal ko grade 10 ko board exam ho jun National Examinations Board (NEB) le conduct garchha. Yo higher secondary education (+2) ko lagi eligibility determine garne important exam ho."
    },
    "dashain": {
        "en": "Dashain is Nepal's biggest and most important festival, celebrated for 15 days in September/October. It symbolizes the victory of good over evil and is a time for family reunions, receiving Tika and blessings from elders.",
        "ne": "दशैं नेपालको सबैभन्दा ठूलो र महत्त्वपूर्ण चाड हो, जुन सेप्टेम्बर/अक्टोबरमा १५ दिनसम्म मनाइन्छ। यसले असत्यमाथि सत्यको विजयलाई प्रतीक गर्दछ र परिवारको पुनर्मिलन, बुजुर्गहरूबाट टीका र आशीर्वाद प्राप्त गर्ने समय हो।",
        "np": "Dashain Nepal ko sabai bhanda thulo ra important festival ho, jun September/October ma 15 din samma manaincha. Yo evil over good ko victory lai symbolize garchha ani family reunion, elder haru bata Tika ra blessings paune time ho."
    },
    "ioe entrance": {
        "en": "IOE (Institute of Engineering) Entrance is the entrance exam for engineering programs at Tribhuvan University. It's highly competitive and covers Physics, Chemistry, Mathematics, and English. Students need strong preparation and typically score 35+ marks out of 100 for admission.",
        "ne": "IOE (Institute of Engineering) Entrance त्रिभुवन विश्वविद्यालयमा इन्जिनियरिङ कार्यक्रमहरूको प्रवेश परीक्षा हो। यो अत्यधिक प्रतिस्पर्धात्मक छ र Physics, Chemistry, Mathematics, र English समावेश गर्दछ। विद्यार्थीहरूलाई बलियो तयारी चाहिन्छ र सामान्यतया १०० मध्ये ३५+ अंक भर्नाको लागि आवश्यक हुन्छ।",
        "np": "IOE (Institute of Engineering) Entrance Tribhuvan University ma engineering programs ko entrance exam ho. Yo highly competitive cha ani Physics, Chemistry, Mathematics, ra English cover garchha. Students lai strong preparation chahincha ani typically 100 madhye 35+ marks admission ko lagi chahincha."
    }
    # Add ALL your FAQs here
}

def create_faq_embeddings():
    """Create embeddings for your FAQs (FREE, OFFLINE)"""
    
    print("Loading embedding model...")
    # This downloads once, then works offline
    model = SentenceTransformer('all-MiniLM-L6-v2')
    print("✓ Model loaded!")
    
    print("\nCreating embeddings for FAQs...")
    
    faq_with_embeddings = {}
    
    for question, answers in FAQ_DATABASE.items():
        print(f"Processing: {question}")
        
        try:
            # Get embedding for the FAQ question
            embedding = model.encode(question)
            
            # Convert to list for JSON storage
            embedding_list = embedding.tolist()
            
            # Store the embedding with the FAQ
            faq_with_embeddings[question] = {
                "answers": answers,
                "embedding": embedding_list,
                "text": question
            }
            
            print(f"  ✓ Got embedding ({len(embedding_list)} numbers)")
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    # Save to file
    with open("faq_embeddings.json", "w", encoding="utf-8") as f:
        json.dump(faq_with_embeddings, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ Saved {len(faq_with_embeddings)} FAQs to faq_embeddings.json")
    return faq_with_embeddings

if __name__ == "__main__":
    create_faq_embeddings()