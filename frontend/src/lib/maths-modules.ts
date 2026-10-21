import { readdir } from 'node:fs/promises';
import path from 'node:path';

// Short labels for the existing curriculum collections. File presence determines
// which modules appear; gaps in the curriculum are never invented as levels.
const labels: Record<number, Record<number, string>> = {
  1: { 1: 'Numbers & adding', 2: 'Make a ten', 3: 'Measuring length', 4: 'Tens & ones', 5: 'Shapes', 6: 'Number stories' },
  2: { 1: 'Make & break ten', 3: 'Place value', 5: 'Add & subtract', 6: 'Equal groups', 7: 'Data & measuring', 8: 'Shapes & parts' },
  3: { 2: 'Time & measuring', 3: 'Multiply & divide', 4: 'Exploring area', 5: 'Fractions', 6: 'Data & graphs', 7: 'Number stories' },
  4: { 1: 'Place value', 2: 'Metric measuring', 3: 'Multiply & divide', 4: 'Lines & angles', 5: 'Fractions', 6: 'Decimals' },
  5: { 1: 'Decimal place value', 2: 'Multiply & divide', 3: 'Adding fractions', 4: 'Fraction operations', 5: 'Volume & shapes' },
};

export async function getMathsModules() {
  const grades = await Promise.all([1, 2, 3, 4, 5].map(async grade => {
    const files = await readdir(path.join(process.cwd(), '..', 'ciriculam', `grade${grade}`));
    const modules = files.flatMap(file => {
      const match = file.match(new RegExp(`^math_g${grade}_m(\\d+)_Lessons\\.json$`));
      if (!match) return [];
      const moduleNumber = Number(match[1]);
      return [{ module: moduleNumber, title: labels[grade]?.[moduleNumber] ?? `Module ${moduleNumber}` }];
    }).sort((a, b) => a.module - b.module);
    return [grade, modules] as const;
  }));
  return Object.fromEntries(grades);
}
