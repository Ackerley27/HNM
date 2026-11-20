import { Construction } from "lucide-react";

const sections = {
  traffic: { title: "วิเคราะห์การจราจร", description: "หน้าวิเคราะห์โปรโตคอลและโฮสต์จะเพิ่มในขั้นถัดไป" },
  departments: { title: "วิเคราะห์รายแผนก", description: "เครื่องมือเปรียบเทียบการใช้งานของแผนกจะเพิ่มในขั้นถัดไป" },
  devices: { title: "อุปกรณ์เครือข่าย", description: "การจัดการอุปกรณ์และประวัติสถานะจะเพิ่มในขั้นถัดไป" },
  alerts: { title: "การแจ้งเตือน", description: "การตั้งค่าเกณฑ์และจัดการเหตุการณ์จะเพิ่มในขั้นถัดไป" },
  reports: { title: "รายงาน", description: "รายงานตามช่วงเวลาและการส่งออกจะเพิ่มในขั้นถัดไป" },
  settings: { title: "ตั้งค่าระบบ", description: "การตั้งค่าแหล่งตรวจวัดจะเพิ่มในขั้นถัดไป" },
};

export default function ComingSoonPage({ section }) {
  const content = sections[section] || sections.traffic;
  return (
    <section className="coming-soon">
      <div className="coming-icon"><Construction size={24} /></div>
      <span className="eyebrow">กำลังพัฒนา</span>
      <h1>{content.title}</h1>
      <p>{content.description}</p>
      <span className="coming-note">ขณะนี้เปิดให้ใช้งานเฉพาะหน้าภาพรวมเครือข่าย</span>
    </section>
  );
}
